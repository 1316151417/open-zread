#!/usr/bin/env python3
"""Serve the generated site locally under /open-zread/."""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parents[1] / "site"
BASE = "/open-zread"
PORT = 8081

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve(head=True)

    def do_HEAD(self):
        self.serve(head=False)

    def serve(self, head: bool):
        path = unquote(urlsplit(self.path).path)
        if path == BASE:
            self.send_response(301)
            self.send_header("Location", f"{BASE}/")
            self.end_headers()
            return
        if not path.startswith(f"{BASE}/"):
            self.send_error(404, "not found")
            return
        rel = path[len(BASE) + 1 :]
        target = (SITE / rel).resolve()
        if not target.is_relative_to(SITE.resolve()):
            self.send_error(404, "not found")
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(404, "not found")
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'",
        )
        self.end_headers()
        if head:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Open Zread 文档预览：http://127.0.0.1:{PORT}{BASE}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
