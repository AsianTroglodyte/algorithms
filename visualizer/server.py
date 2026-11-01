"""Loopback-only browser companion, running outside the suspended debuggee."""

import argparse
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).with_name("static")


def create_server(port=0, token=None):
    token = token or secrets.token_urlsafe(24)
    state = {"status": "waiting", "message": "Waiting for a registered tree", "nodes": [], "edges": [], "warnings": []}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, code, body, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def authorized_path(self):
            prefix = f"/{token}/"
            return self.path[len(prefix):] if self.path.startswith(prefix) else None

        def do_GET(self):
            path = self.authorized_path()
            if path == "state":
                with lock:
                    body = json.dumps(state).encode()
                self.respond(200, body)
            elif path in ("", "app.js", "style.css"):
                name, mime = {"": ("index.html", "text/html; charset=utf-8"), "app.js": ("app.js", "text/javascript"), "style.css": ("style.css", "text/css")}[path]
                self.respond(200, (STATIC / name).read_bytes(), mime)
            else:
                self.respond(404, b'{}')

        def do_POST(self):
            if self.authorized_path() != "state":
                self.respond(404, b'{}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 10_000_000:
                    raise ValueError("Invalid payload size")
                update = json.loads(self.rfile.read(length))
                if not isinstance(update, dict) or update.get("status") not in ("waiting", "paused", "running", "ended", "error"):
                    raise ValueError("Invalid state")
                with lock:
                    state.update(update)
                    state["message"] = update.get("message", "")
                    state["revision"] = state.get("revision", 0) + 1
                self.respond(200, b'{}')
            except (ValueError, json.JSONDecodeError):
                self.respond(400, b'{}')

    return ThreadingHTTPServer(("127.0.0.1", port), Handler), token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server, token = create_server(args.port)
    print(f"http://127.0.0.1:{server.server_port}/{token}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
