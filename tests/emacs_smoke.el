;;; emacs_smoke.el --- Real dap-mode/debugpy smoke test -*- lexical-binding: t; -*-

;; Load installed packages without loading or modifying the user's Emacs config.
(dolist (base (list (expand-file-name ".local/elpa" user-emacs-directory)
                   (expand-file-name ".local/straight/build-30.2" user-emacs-directory)))
  (when (file-directory-p base)
    (dolist (dir (directory-files base t "^[^.].*"))
      (when (file-directory-p dir) (add-to-list 'load-path dir)))))
(load-file (expand-file-name "../rb-visualizer.el"
                             (file-name-directory load-file-name)))
(require 'ert)

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

(defun rb-test--launch-and-pause ()
  (let* ((default-directory rb-visualizer-directory)
         (dap-breakpoints-file (make-temp-file "rb-breakpoints-"))
         (dap--breakpoints (make-hash-table :test 'equal))
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
            (search-forward "    rotate_down.parent = rotate_up")
            (dap-breakpoint-add)
            (advice-add 'rb-visualizer--publish :after publisher)
            (rb-visualizer-debug)
            (while (and (not ended) (not failure) (< (float-time) deadline))
              (accept-process-output nil .1))
            (should-not failure)
            (should launched)
            (should ended)
            (should paused)
            (should (seq-some (lambda (node) (member "rotate_down" (append (alist-get 'names node) nil)))
                             (append (alist-get 'nodes paused) nil)))
            (let ((state (rb-test--server-state)))
              (should (equal (alist-get 'status state) "ended"))
              (should (> (length (alist-get 'nodes state)) 0)))
            (should (plist-get (dap--debug-session-launch-args rb-visualizer--session)
                               :rb-visualizer))
            (dap--debug-session-name rb-visualizer--session))
        (advice-remove 'rb-visualizer--publish publisher)
        (when (process-live-p rb-visualizer--server) (delete-process rb-visualizer--server))
        (delete-file dap-breakpoints-file)))))

(ert-deftest rb-real-emacs-repeated-launch-and-pause ()
  ;; dap-mode changes :name on subsequent launches. Both sessions must publish
  ;; snapshots through HTTP, regardless of the generated display name.
  (let ((first (rb-test--launch-and-pause))
        (second (rb-test--launch-and-pause)))
    (should-not (equal first second))))

(ert-run-tests-batch-and-exit)
