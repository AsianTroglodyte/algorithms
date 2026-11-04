;;; rb-visualizer.el --- Tree companion for dap-mode -*- lexical-binding: t; -*-

(require 'cl-lib)
(require 'json)
(require 'url)
(require 'browse-url)
(require 'dap-mode)
(require 'dap-python)
(require 'dap-ui)

(defvar rb-visualizer-directory
  (file-name-as-directory
   (expand-file-name "../.." (file-name-directory (or load-file-name buffer-file-name))))
  "Repository root containing the tree, examples, and Python companion.")
(defvar rb-visualizer-python
  (expand-file-name ".venv/bin/python" rb-visualizer-directory)
  "Python interpreter with debugpy installed.")
(defvar rb-visualizer-example "examples.visualizer_demo"
  "Default choice for `rb-visualizer-debug-example'.")
(defvar rb-visualizer--server nil)
(defvar rb-visualizer--url nil)
(defvar rb-visualizer--generation 0)
(defvar rb-visualizer--session nil)

(defun rb-visualizer--session-p (session)
  "Return non-nil for a tree visualizer SESSION."
  (and session
       (plist-get (dap--debug-session-launch-args session) :rb-visualizer)))

(defun rb-visualizer--check-stopped (session &optional thread-id)
  "Explain why SESSION cannot step, before dap-mode sends a request."
  (when (rb-visualizer--session-p session)
    (unless (and (dap--session-running session)
                 (process-live-p (dap--debug-session-proc session)))
      (user-error "Tree debug session ended; run M-x rb-visualizer-debug or M-x rb-visualizer-debug-example to start again"))
    (unless (or thread-id (dap--debug-session-thread-id session))
      (user-error "Python is running; wait for a breakpoint before stepping"))))

(defun rb-visualizer--step (original command session)
  "Check the tree SESSION before invoking ORIGINAL for COMMAND."
  (rb-visualizer--check-stopped session)
  (funcall original command session))

(advice-add 'dap--step :around #'rb-visualizer--step)
(advice-add 'dap-continue :before #'rb-visualizer--check-stopped)

(defun rb-visualizer--watch-process (session)
  "Distinguish normal DAP cleanup from an unexpected adapter exit in SESSION."
  (when (rb-visualizer--session-p session)
    (let* ((process (dap--debug-session-proc session))
           (sentinel (process-sentinel process)))
      (set-process-sentinel
       process
       (lambda (proc event)
         ;; dap-mode deletes its adapter on every exited/terminated event.
         ;; Its sentinel otherwise describes successful cleanup as "killed".
         (if (process-get proc 'rb-visualizer-expected-end)
             (unless (eq (dap--debug-session-state session) 'terminated)
               (dap--mark-session-as-terminated session))
           (when sentinel (funcall sentinel proc event)))))))
  session)

(advice-add 'dap--create-session :filter-return #'rb-visualizer--watch-process)

(defun rb-visualizer--terminal-event (original session event)
  "Record Python termination before ORIGINAL cleans up SESSION's adapter."
  (when (and (rb-visualizer--session-p session)
             (member (gethash "event" event) '("exited" "terminated")))
    (let ((process (dap--debug-session-proc session)))
      (process-put process 'rb-visualizer-expected-end t)
      (when (equal (gethash "event" event) "exited")
        (process-put process 'rb-visualizer-exit-code
                     (gethash "exitCode" (gethash "body" event))))))
  (funcall original session event))

(advice-add 'dap--on-event :around #'rb-visualizer--terminal-event)

(defun rb-visualizer--breakpoint-buffers ()
  "Find open breakpoint buffers without requiring live breakpoint markers.
Persisted breakpoints and breakpoints in closed files have only :point.
The installed dap-mode assumes :marker exists when refreshing breakpoints,
which otherwise raises `wrong-type-argument' during debug process events.
Keep all breakpoint records; dap-mode restores markers in visiting buffers."
  (let (buffers)
    (maphash (lambda (file breakpoints)
               (when breakpoints
                 (when-let ((buffer (find-buffer-visiting file)))
                   (cl-pushnew buffer buffers))))
             (dap--get-breakpoints))
    (nreverse buffers)))

;; Use filenames, which survive saving/reopening files, rather than the first
;; breakpoint's optional marker.  This also covers session termination.
(advice-add 'dap--buffers-w-breakpoints :override #'rb-visualizer--breakpoint-buffers)

(defun rb-visualizer--publish (state)
  "Send STATE to the independent server, including while Python is suspended."
  (when rb-visualizer--url
    (condition-case err
        (let* ((url-request-method "POST")
               (url-request-extra-headers '(("Content-Type" . "application/json")))
               (url-request-data (encode-coding-string (json-encode state) 'utf-8))
               (url-show-status nil)
               (url-proxy-services nil)
               (buffer (url-retrieve-synchronously
                        (concat rb-visualizer--url "state") t t 2)))
          (when buffer (kill-buffer buffer)))
      (error (message "Tree companion: %s" (error-message-string err))))))

(defun rb-visualizer--current-p (session generation)
  (and (eq session rb-visualizer--session)
       (dap--session-running session)
       (= generation rb-visualizer--generation)))

(defun rb-visualizer--snapshot (session thread-id)
  "Request the top stopped frame, independent of Emacs's selected frame."
  (let ((generation (cl-incf rb-visualizer--generation)))
    (dap--send-message
     (dap--make-request "stackTrace" (list :threadId thread-id :startFrame 0 :levels 1))
     (lambda (response)
       (when (rb-visualizer--current-p session generation)
         (let* ((frames (gethash "stackFrames" (gethash "body" response)))
                (frame (and frames (> (length frames) 0) (elt frames 0))))
           (if (not frame)
               (rb-visualizer--publish '((status . "error") (message . "No stopped frame available")))
             (dap--send-message
              (dap--make-request
               "evaluate"
               (list :frameId (gethash "id" frame) :context "repl"
                     :expression "__import__('visualizer.runtime', fromlist=['snapshot_wire']).snapshot_wire(locals())"))
              (lambda (result)
                (when (rb-visualizer--current-p session generation)
                  (condition-case err
                      (let* ((wire (gethash "result" (gethash "body" result)))
                             (json-object-type 'alist)
                             (json-array-type 'vector))
                        (unless (and (gethash "success" result)
                                     (stringp wire)
                                     (string-match "\\`['\"]\\([0-9a-f]+\\)['\"]\\'" wire))
                          (error "%s" (or (gethash "message" result) "Unexpected snapshot response")))
                        (rb-visualizer--publish
                         (json-read-from-string
                          (decode-coding-string
                           (let ((hex (match-string 1 wire)))
                             (apply #'unibyte-string
                                    (cl-loop for i from 0 below (length hex) by 2
                                             collect (string-to-number (substring hex i (+ i 2)) 16))))
                           'utf-8))))
                    (error
                     (rb-visualizer--publish
                      `((status . "error") (message . ,(error-message-string err))))))))
              session)))))
     session)))

(defun rb-visualizer--event (session event)
  "Observe DAP events without changing ordinary debugger commands."
  (when (and rb-visualizer--url
             (rb-visualizer--session-p session)
             (dap--session-running session))
    (setq rb-visualizer--session session)
    (pcase (gethash "event" event)
      ("stopped"
       (rb-visualizer--snapshot session (gethash "threadId" (gethash "body" event))))
      ("continued"
       (cl-incf rb-visualizer--generation)
       (rb-visualizer--publish '((status . "running") (message . "")))))))

(defun rb-visualizer--ended (session)
  (when (eq session rb-visualizer--session)
    (let ((process (dap--debug-session-proc session)))
      (unless (process-get process 'rb-visualizer-ended)
        (process-put process 'rb-visualizer-ended t)
        (cl-incf rb-visualizer--generation)
        (let* ((expected (process-get process 'rb-visualizer-expected-end))
               (code (process-get process 'rb-visualizer-exit-code))
               (text (if expected
                         (format "Python session ended%s. Start another run with M-x rb-visualizer-debug or M-x rb-visualizer-debug-example."
                                 (if code (format " (exit code %s)" code) ""))
                       (format "Debug adapter exited unexpectedly; inspect %s and %s."
                               (buffer-name (dap--debug-session-output-buffer session))
                               (format "*%s stderr*" (dap--debug-session-name session))))))
          (rb-visualizer--publish `((status . ,(if expected "ended" "error"))
                                   (message . ,text)))
          (message "Tree companion: %s" text))))))

(advice-add 'dap--on-event :after #'rb-visualizer--event)
(add-hook 'dap-terminated-hook #'rb-visualizer--ended)

(defun rb-visualizer--launch (target)
  "Launch the captured program or module in TARGET once the server is ready."
  (browse-url rb-visualizer--url)
  (let ((default-directory rb-visualizer-directory)
        (dap-python-executable rb-visualizer-python)
        ;; dap-python otherwise adds the current file as an argument to modules.
        (buffer-file-name nil)
        (pythonpath (getenv "PYTHONPATH")))
    (condition-case err
        (dap-debug (append
                    (list :type "python" :debugger 'debugpy
                          :request "launch" :name "Red-black tree"
                          :rb-visualizer t
                          :env (list :PYTHONPATH
                                     (concat rb-visualizer-directory
                                             (when (and pythonpath (not (equal pythonpath "")))
                                               (concat path-separator pythonpath))))
                          :cwd rb-visualizer-directory :console "internalConsole"
                          :stopOnEntry t :justMyCode t
                          :rules (vector
                                  (list :path (expand-file-name "visualizer/runtime.py" rb-visualizer-directory)
                                        :include json-false)))
                    target))
      (error (rb-visualizer--publish
              `((status . "error") (message . ,(error-message-string err))))))))

;;;###autoload
(defun rb-visualizer-debug ()
  "Save and debug the current Python file with the browser visualizer.
The program must install node tracking and register its tree, as the examples do."
  (interactive)
  (unless (and buffer-file-name (string-match-p "\\.pyw?\\'" buffer-file-name))
    (user-error "Visit a Python file to debug the current buffer"))
  (when (or (buffer-modified-p) (not (file-exists-p buffer-file-name)))
    (save-buffer))
  (unless (file-readable-p buffer-file-name)
    (user-error "Cannot read Python file: %s" buffer-file-name))
  (rb-visualizer--start (list :program (expand-file-name buffer-file-name))))

;;;###autoload
(defun rb-visualizer-debug-example (&optional module)
  "Choose and debug an example MODULE with the browser visualizer."
  (interactive
   (list
    (completing-read
     "Example module: "
     (mapcar (lambda (file) (concat "examples." (file-name-base file)))
             (directory-files (expand-file-name "examples" rb-visualizer-directory)
                              nil "^[^_].*\\.py$"))
     nil t nil nil rb-visualizer-example)))
  (setq rb-visualizer-example (or module rb-visualizer-example))
  (rb-visualizer--start (list :module rb-visualizer-example)))

(defun rb-visualizer--start (target)
  "Start the server and arrange to launch the captured TARGET."
  (when (and rb-visualizer--session (dap--session-running rb-visualizer--session))
    (user-error "End the current tree debug session before launching another"))
  (unless (file-executable-p rb-visualizer-python)
    (user-error "Create .venv and install visualizer/requirements.txt first"))
  (when (process-live-p rb-visualizer--server)
    (delete-process rb-visualizer--server))
  (setq rb-visualizer--url nil rb-visualizer--session nil)
  (cl-incf rb-visualizer--generation)
  (let ((default-directory rb-visualizer-directory)
        (output ""))
    (setq rb-visualizer--server
          (make-process
           :name "rb-visualizer-server" :buffer "*Tree companion server*"
           :command (list rb-visualizer-python "-m" "visualizer.server")
           :noquery t :connection-type 'pipe
           :filter (lambda (_process chunk)
                     (setq output (concat output chunk))
                     (when (and (not rb-visualizer--url)
                                (string-match "http://127\\.0\\.0\\.1:[0-9]+/[A-Za-z0-9_-]+/" output))
                       (setq rb-visualizer--url (match-string 0 output))
                       (run-at-time 0 nil #'rb-visualizer--launch target)))
           :sentinel (lambda (_process event)
                       (unless (string= event "run\n")
                         (message "Tree companion server: %s" (string-trim event))))))))

;;;###autoload
(defun rb-visualizer-stop ()
  "Stop the companion server after finishing a demo."
  (interactive)
  (when (and rb-visualizer--session (dap--session-running rb-visualizer--session))
    (user-error "End the Python debug session first"))
  (when (process-live-p rb-visualizer--server)
    (delete-process rb-visualizer--server))
  (setq rb-visualizer--url nil))

(provide 'rb-visualizer)
;;; rb-visualizer.el ends here
