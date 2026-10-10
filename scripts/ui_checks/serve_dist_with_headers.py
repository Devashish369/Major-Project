"""Serve frontend/dist on :5173 with the SAME response headers render.yaml gives the static site
(the API address in connect-src is swapped for localhost), so the Content-Security-Policy can be
tested before deploying.  SPA fallback: unknown paths serve index.html, like the Render rewrite.

    cd frontend && VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run build
    python scripts/ui_checks/serve_dist_with_headers.py
"""
import http.server
import os
import re
import socketserver

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DIST = os.path.join(ROOT, "frontend", "dist")
yaml_text = open(os.path.join(ROOT, "render.yaml"), encoding="utf8").read()
HEADERS = []
for path, name, value in re.findall(r"- path: (\S+)\s+name: (\S+)\s+value: (.+)", yaml_text):
    value = value.strip().strip('"')
    value = value.replace("https://intellipm-api.onrender.com", "http://localhost:8000")
    value = value.replace("wss://intellipm-api.onrender.com", "ws://localhost:8000")
    HEADERS.append((path, name, value))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def end_headers(self):
        for path, name, value in HEADERS:
            if path == "/*" or (path.endswith("/*") and self.path.startswith(path[:-1])):
                self.send_header(name, value)
        super().end_headers()

    def send_head(self):
        target = os.path.join(DIST, self.path.split("?")[0].lstrip("/"))
        if not os.path.exists(target) or self.path == "/":
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, *args):
        pass


print(f"{len(HEADERS)} header rules from render.yaml; serving {DIST} on http://localhost:5173")
socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("127.0.0.1", 5173), Handler) as httpd:
    httpd.serve_forever()
