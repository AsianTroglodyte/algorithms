;;; rb-visualizer.el --- Tree companion for dap-mode -*- lexical-binding: t; -*-

(require 'cl-lib)
(require 'json)
(require 'url)
(require 'browse-url)
(require 'dap-mode)
(require 'dap-python)
(require 'dap-ui)

(defvar rb-visualizer-directory
  (file-name-directory (or load-file-name buffer-file-name))
  "Directory containing this file and the Python companion.")
(defvar rb-visualizer-python
  (expand-file-name ".venv/bin/python" rb-visualizer-directory)
  "Python interpreter with debugpy installed.")
(defvar rb-visualizer--server nil)
(defvar rb-visualizer--url nil)
(defvar rb-visualizer--generation 0)
(defvar rb-visualizer--session nil)

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
             (equal (plist-get (dap--debug-session-launch-args session) :name)
                    "Red-black tree demo"))
    (setq rb-visualizer--session session)
    (pcase (gethash "event" event)
      ("stopped"
       (rb-visualizer--snapshot session (gethash "threadId" (gethash "body" event))))
      ("continued"
       (cl-incf rb-visualizer--generation)
       (rb-visualizer--publish '((status . "running") (message . "")))))))

(defun rb-visualizer--ended (session)
  (when (eq session rb-visualizer--session)
    (cl-incf rb-visualizer--generation)
    (rb-visualizer--publish '((status . "ended") (message . "")))))

(advice-add 'dap--on-event :after #'rb-visualizer--event)
(add-hook 'dap-terminated-hook #'rb-visualizer--ended)

(defun rb-visualizer--launch ()
  (browse-url rb-visualizer--url)
  (let ((default-directory rb-visualizer-directory)
        (dap-python-executable rb-visualizer-python))
    (condition-case err
        (dap-debug (list :type "python" :debugger 'debugpy
                         :request "launch" :name "Red-black tree demo"
                         :program (expand-file-name "visualizer_demo.py" rb-visualizer-directory)
                         :cwd rb-visualizer-directory :console "internalConsole"
                         :stopOnEntry t :justMyCode t))
      (error (rb-visualizer--publish
              `((status . "error") (message . ,(error-message-string err))))))))

;;;###autoload
(defun rb-visualizer-debug ()
  "Start server, browser and Python debug session with one command."
  (interactive)
  (when (and rb-visualizer--session (dap--session-running rb-visualizer--session))
    (user-error "End the current tree debug session before launching another"))
  (unless (file-executable-p rb-visualizer-python)
    (user-error "Create .venv and install requirements-visualizer.txt first"))
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
                       (run-at-time 0 nil #'rb-visualizer--launch)))
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
