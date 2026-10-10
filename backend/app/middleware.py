"""
middleware.py – network-security headers, request size limit and Server-Timing.

Plain ASGI middleware (no BaseHTTPMiddleware overhead).  WebSocket connections pass through.

Security headers on every API response:
  X-Content-Type-Options: nosniff        browsers must not guess a different content type
  X-Frame-Options: DENY + CSP frame-ancestors 'none'   the API can't be framed (clickjacking)
  Content-Security-Policy: default-src 'none'          JSON never runs scripts (not on /docs)
  Referrer-Policy: no-referrer, Permissions-Policy: no camera / microphone / location
  Strict-Transport-Security            browsers use HTTPS only for a year (Render serves HTTPS)
  Cache-Control: no-store              private project data is not kept in shared caches
Requests with a body larger than 1 MB are refused with 413 before they are read.

Server-Timing: "app;dur=…, db;dur=…;desc=\"N queries\"" – visible in the browser's
DevTools → Network → Timing, so slow requests can be explained (time in our code vs. database).
"""
import json
import time

from app.database import query_stats

MAX_BODY_BYTES = 1_000_000
_DOCS = ("/docs", "/redoc", "/openapi.json")

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"cross-origin-opener-policy", b"same-origin"),
]
_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


class SecurityAndTimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > MAX_BODY_BYTES
                except ValueError:
                    too_big = True
                if too_big:
                    body = json.dumps({"success": False, "message": "Request body too large (max 1 MB).",
                                       "errors": [], "detail": "Request body too large (max 1 MB)."}).encode()
                    await send({"type": "http.response.start", "status": 413,
                                "headers": [(b"content-type", b"application/json"),
                                            (b"content-length", str(len(body)).encode())] + _SECURITY_HEADERS})
                    await send({"type": "http.response.body", "body": body})
                    return
                break

        path = scope.get("path", "")
        stats = [0, 0.0]                    # [queries, seconds] filled by database.py
        token = query_stats.set(stats)
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                total_ms = (time.perf_counter() - start) * 1000
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                headers += [h for h in _SECURITY_HEADERS if h[0] not in existing]
                if not path.startswith(_DOCS):
                    headers.append(_API_CSP)
                    if b"cache-control" not in existing:
                        headers.append((b"cache-control", b"no-store"))
                timing = f'app;dur={total_ms:.1f}, db;dur={stats[1] * 1000:.1f};desc="{stats[0]} queries"'
                headers += [(b"server-timing", timing.encode()), (b"timing-allow-origin", b"*")]
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            query_stats.reset(token)
