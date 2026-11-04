;;; emacs_smoke.el --- Real dap-mode/debugpy smoke test -*- lexical-binding: t; -*-

;; Load installed packages without loading or modifying the user's Emacs config.
(dolist (base (list (expand-file-name ".local/elpa" user-emacs-directory)
                   (expand-file-name ".local/straight/build-30.2" user-emacs-directory)))
  (when (file-directory-p base)
    (dolist (dir (directory-files base t "^[^.].*"))
      (when (file-directory-p dir) (add-to-list 'load-path dir)))))
(load-file (expand-file-name "../emacs/rb-visualizer.el"
                             (file-name-directory load-file-name)))
(require 'ert)

;; Select an insertion-only lesson to avoid the original demo's deletion path:
;; RB_TEST_EXAMPLE=examples.insert_case1_nil emacs --batch -Q -l visualizer/tests/emacs_smoke.el
(setq rb-visualizer-example (or (getenv "RB_TEST_EXAMPLE") "examples.insert_case1_internal"))
(defvar rb-test--case1 (string-prefix-p "examples.insert_case1_" rb-visualizer-example))

(defun rb-test--server-state ()
  (let* ((url-proxy-services nil)
         (json-object-type 'alist)
         (buffer (url-retrieve-synchronously
                  (concat rb-visualizer--url "state") t t 2)))
    (unless buffer (error "Companion state endpoint did not respond"))
    (unwind-protect
        (with-current-buffer buffer
          (goto-char url-http-end-of-headers)
          (json-read))
      (kill-buffer buffer))))

(defun rb-test--launch-and-pause (&optional choose-example)
  (let* ((default-directory rb-visualizer-directory)
         (dap-breakpoints-file (make-temp-file "rb-breakpoints-"))
         (dap--breakpoints (make-hash-table :test 'equal))
         (closed-file (make-temp-file "rb-closed-breakpoint-" nil ".py" "pass\n"))
         (launched nil) (paused nil) (ended nil) (failure nil)
         (deadline (+ (float-time) 40))
         (publisher
          (lambda (state)
            (pcase (alist-get 'status state)
              ("waiting" (run-at-time .1 nil #'call-interactively #'dap-continue))
              ("paused"
               (setq paused state)
               (run-at-time .1 nil #'call-interactively #'dap-continue))
              ("ended" (setq ended t))
              ("error" (setq failure state))))))
    (cl-letf (((symbol-function 'browse-url) (lambda (_url &rest _args) (setq launched t)))
              ((symbol-function 'dap--persist-breakpoints) #'ignore))
      (unwind-protect
          (progn
            (find-file (expand-file-name "red_black_trees.py" rb-visualizer-directory))
            (goto-char (point-min))
            (search-forward (if rb-test--case1
                                "    while fix_node.parent.color == Color.RED:"
                              "    rotate_down.parent = rotate_up"))
            (dap-breakpoint-add)
            (find-file (expand-file-name
                        (concat (replace-regexp-in-string "\\." "/" rb-visualizer-example) ".py")
                        rb-visualizer-directory))
            ;; Closed files retain :point but no :marker in dap-mode.
            ;; They must not break process filters or termination refreshes.
            (puthash closed-file (list (list :point 1 :condition "True"))
                     (dap--get-breakpoints))
            (advice-add 'rb-visualizer--publish :after publisher)
            (if choose-example
                (cl-letf (((symbol-function 'completing-read)
                           (lambda (&rest _args) rb-visualizer-example)))
                  (call-interactively #'rb-visualizer-debug-example))
              (call-interactively #'rb-visualizer-debug))
            ;; The server starts asynchronously. Changing buffers must not
            ;; change which file/module the debugger will launch.
            (switch-to-buffer (get-buffer-create "*rb launch focus changed*"))
            (while (and (not ended) (not failure) (< (float-time) deadline))
              (accept-process-output nil .1))
            (should-not failure)
            (should launched)
            (should ended)
            (should-not (dap--session-running rb-visualizer--session))
            (should (equal (process-get (dap--debug-session-proc rb-visualizer--session)
                                       'rb-visualizer-exit-code) 0))
            (should (string-match-p "Tree debug session ended"
                                   (error-message-string
                                    (should-error (call-interactively #'dap-next)
                                                  :type 'user-error))))
            (should (equal (gethash closed-file (dap--get-breakpoints))
                           '((:point 1 :condition "True"))))
            (should paused)
            (should (seq-some (lambda (node) (member (if rb-test--case1 "fix_node" "rotate_down")
                                                   (append (alist-get 'names node) nil)))
                             (append (alist-get 'nodes paused) nil)))
            (let ((state (rb-test--server-state)))
              (should (equal (alist-get 'status state) "ended"))
              (should (string-match-p "exit code 0" (alist-get 'message state)))
              (should (> (length (alist-get 'nodes state)) 0)))
            (should (plist-get (dap--debug-session-launch-args rb-visualizer--session)
                               :rb-visualizer))
            (let ((args (dap--debug-session-launch-args rb-visualizer--session)))
              (if choose-example
                  (should (equal (plist-get args :module) rb-visualizer-example))
                (should (equal (plist-get args :program)
                               (expand-file-name
                                (concat (replace-regexp-in-string "\\." "/" rb-visualizer-example) ".py")
                                rb-visualizer-directory))))
              (should (equal (plist-get args :args) [])))
            (dap--debug-session-name rb-visualizer--session))
        (advice-remove 'rb-visualizer--publish publisher)
        (when (process-live-p rb-visualizer--server) (delete-process rb-visualizer--server))
        (remhash closed-file (dap--get-breakpoints))
        (delete-file closed-file)
        (delete-file dap-breakpoints-file)))))

(ert-deftest rb-real-emacs-repeated-launch-and-pause ()
  ;; dap-mode changes :name on subsequent launches. Both sessions must publish
  ;; snapshots through HTTP, regardless of the generated display name.
  (let ((first (rb-test--launch-and-pause))
        (second (rb-test--launch-and-pause t)))
    (should-not (equal first second))))

(ert-deftest rb-current-buffer-requires-a-python-file ()
  (with-temp-buffer
    (should-error (call-interactively #'rb-visualizer-debug) :type 'user-error)
    (let ((buffer-file-name "/tmp/rb-not-python.txt"))
      (should-error (call-interactively #'rb-visualizer-debug) :type 'user-error))))

(ert-deftest rb-launch-skips-visualization-runtime-when-stepping ()
  (let (launched)
    (cl-letf (((symbol-function 'browse-url) #'ignore)
              ((symbol-function 'dap-debug) (lambda (config) (setq launched config))))
      (rb-visualizer--launch '(:module "examples.delete_red_root")))
    (let* ((rules (plist-get launched :rules))
           (rule (aref rules 0)))
      (should (equal (plist-get rule :path)
                     (expand-file-name "visualizer/runtime.py" rb-visualizer-directory)))
      (should (eq (plist-get rule :include) json-false))
      (should (string-match-p "\"include\":false" (json-encode rules))))))

(ert-deftest rb-step-checks-lifecycle-only-for-tree-sessions ()
  (let* ((process (make-process :name "rb-step-test" :command '("cat") :noquery t))
         (session (make-dap--debug-session :proc process :state 'running
                                          :launch-args '(:rb-visualizer t)))
         (requests 0))
    (unwind-protect
        (cl-letf (((symbol-function 'dap--send-message)
                   (lambda (&rest _) (cl-incf requests))))
          (should (string-match-p "Python is running"
                                 (error-message-string
                                  (should-error (dap-next session) :type 'user-error))))
          (should (= requests 0))
          (setf (dap--debug-session-thread-id session) 1)
          (dap-next session)
          (should (= requests 1))
          (setf (dap--debug-session-state session) 'terminated)
          (should-error (dap-next session) :type 'user-error)
          (should-error (dap-continue session 1) :type 'user-error)
          (should (= requests 1))
          ;; Other debugger sessions retain dap-mode's own behavior.
          (setf (dap--debug-session-launch-args session) nil)
          (let (called)
            (rb-visualizer--step (lambda (&rest _) (setq called t)) "next" session)
            (should called)))
      (delete-process process))))

(ert-deftest rb-unexpected-adapter-exit-is-an-error ()
  (let* ((process (make-process :name "rb-exit-test" :command '("cat") :noquery t))
         (session (make-dap--debug-session :proc process :state 'running
                                          :name "test adapter"
                                          :output-buffer (get-buffer-create "*rb test out*")
                                          :launch-args '(:rb-visualizer t)))
         (rb-visualizer--session session)
         (rb-visualizer--generation 0)
         states)
    (unwind-protect
        (cl-letf (((symbol-function 'rb-visualizer--publish)
                   (lambda (state) (push state states))))
          (set-process-sentinel process (lambda (&rest _) (rb-visualizer--ended session)))
          (rb-visualizer--watch-process session)
          (delete-process process)
          (should (= (length states) 1))
          (should (equal (alist-get 'status (car states)) "error"))
          (should (string-match-p "exited unexpectedly" (alist-get 'message (car states))))
          (rb-visualizer--ended session)
          (should (= (length states) 1))
          (should (= rb-visualizer--generation 1)))
      (when (process-live-p process) (delete-process process))
      (kill-buffer "*rb test out*"))))

(ert-deftest rb-ended-session-rejects-late-snapshots-and-events ()
  (let* ((session (make-dap--debug-session :state 'terminated
                                         :launch-args '(:rb-visualizer t)))
         (rb-visualizer--session session)
         (rb-visualizer--generation 10)
         (rb-visualizer--url "http://unused/")
         (event (make-hash-table :test 'equal)))
    (should-not (rb-visualizer--current-p session 10))
    (puthash "event" "continued" event)
    (cl-letf (((symbol-function 'rb-visualizer--publish)
               (lambda (&rest _) (ert-fail "Ended session published a stale event"))))
      (rb-visualizer--event session event))
    (should (= rb-visualizer--generation 10))))

(ert-deftest rb-breakpoint-refresh-preserves-unopened-files ()
  (let* ((file (make-temp-file "rb-breakpoint-refresh-" nil ".py" "pass\n"))
         (breakpoints (make-hash-table :test 'equal))
         (record (list :point 1 :condition "True" :hit-condition "2" :log-message "hello"))
         (dead-marker (make-marker))
         buffer)
    (unwind-protect
        (cl-letf (((symbol-function 'dap--get-breakpoints) (lambda () breakpoints)))
          (puthash file (list record) breakpoints)
          (puthash "/tmp/rb-closed-buffer.py" (list (list :point 1)) breakpoints)
          (puthash "/tmp/rb-dead-marker.py" (list (list :point 1 :marker dead-marker)) breakpoints)
          (puthash "/tmp/rb-empty-breakpoints.py" nil breakpoints)
          (should-not (dap--buffers-w-breakpoints))
          (should-not (dap--refresh-breakpoints))
          (should (= (hash-table-count breakpoints) 4))
          (setq buffer (find-file-noselect file))
          ;; Refresh must reestablish a marker for the reopened file, while
          ;; keeping positions, conditions, hit conditions and log messages.
          (should (equal (dap--buffers-w-breakpoints) (list buffer)))
          (dap--refresh-breakpoints)
          (should (eq (marker-buffer (plist-get record :marker)) buffer))
          (should (= (marker-position (plist-get record :marker)) 1))
          (dolist (property '(:point :condition :hit-condition :log-message))
            (should (equal (plist-get record property)
                           (plist-get '(:point 1 :condition "True" :hit-condition "2" :log-message "hello") property))))
          (should (equal (gethash "/tmp/rb-closed-buffer.py" breakpoints) '((:point 1))))
          (should (= (hash-table-count breakpoints) 4)))
      (when (buffer-live-p buffer) (kill-buffer buffer))
      (delete-file file))))

(ert-run-tests-batch-and-exit)
