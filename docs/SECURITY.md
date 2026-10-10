# Security in IntelliPM

The four areas of a cybersecurity curriculum (network & system security, ethical hacking & penetration
testing, cryptography & security protocols, threat detection & digital forensics), applied to this app.
Every item is in the code and covered by `backend/tests/test_security.py` (19 tests) or a browser check.

## 1. Network & system security

| Control | Where |
|---|---|
| HTTPS everywhere (Render TLS) + `Strict-Transport-Security` (1 year) | Render, `app/middleware.py` |
| API headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cache-Control: no-store` | `app/middleware.py` |
| Website headers: a strict Content-Security-Policy (scripts only from the site itself; API and fonts allow-listed), clickjacking protection, `nosniff`, referrer and permissions policies | `render.yaml` → `headers` (checked with `scripts/ui_checks/csp_check.py`) |
| CORS: only the frontend origin; only the methods and headers the app uses | `app/main.py` |
| Request bodies over 1 MB refused (413); every text, list and skill map has a maximum size | `app/middleware.py`, `app/schemas.py` |
| Errors never expose stack traces or SQL; every error uses one JSON envelope | `app/main.py` |
| Secrets only in environment variables; the app refuses to start on PostgreSQL with the default `SECRET_KEY`; no secret has ever been committed (whole git history scanned) | `app/config.py` |
| Dependencies scanned: `pip-audit` (backend) and `npm audit` (frontend) report **0 known vulnerabilities** (2026-10-11) | see `docs/TESTING_REPORT.md` |

## 2. Ethical hacking & penetration testing

The attacks a tester would try first, and the result. All are automated tests, so they run on every change.

| Attack | Result |
|---|---|
| Guess a password repeatedly (brute force) | Blocked after 5 failures for that email from that network (HTTP 429 + Retry-After); 20 from any network; 50 per network across emails |
| Find out which emails are registered | Same message **and the same bcrypt work** for an unknown email and a wrong password |
| Forge a token (wrong key, `alg: none`, no expiry, expired, garbage) | 401 |
| Reuse a token after a password change / "sign out everywhere" | 401, also for the live-updates WebSocket |
| Read another team's project, tasks, decisions, skill gaps (IDOR) | 404 (non-members cannot even learn the project exists); admin-only actions 403 |
| Assign a task to someone outside the project, or send a malformed assignment list | Ignored / 422 – never a server error |
| Send a 100-character or 1 MB password, a huge body | 422 / 413 – previously a 73+ byte password crashed registration (bcrypt 5) |
| Store `<script>` in a task title | Shown as text: React escapes it and nothing uses `innerHTML`; the CSP would block it anyway |
| Use up the free AI quota with one account | Per-user limits on plan / ask / estimate (429) |
| Create accounts in bulk | 30 per network per hour (429) |
| SQL injection | All queries are SQLAlchemy expressions with bound parameters; the only raw SQL (start-up migration) uses fixed table names and bound values |

Permission matrix from the final review: 47/47 checks (see `docs/TESTING_REPORT.md`).

## 3. Cryptography & security protocols

| Control | Where |
|---|---|
| Passwords hashed with **bcrypt** (salted, slow by design); constant-time comparison | `app/security.py` |
| Password policy: 8–72 bytes, a letter and a number, not one of the most common passwords, not the username or email; checked in the browser and on the server | `app/schemas.py`, `frontend/src/api/passwordPolicy.js` |
| Sessions are **JWT HS256** tokens, 12 h expiry, algorithm pinned (no `none`), `exp` and `sub` required | `app/security.py` |
| **Token versions**: every token carries the account's version; changing the password or "Sign out everywhere" raises it and every older token stops working at once | `app/models.py` (`users.token_version`), `app/deps.py`, `app/routers/ws.py` |
| Change password requires the current password and returns a fresh token for the current tab | `POST /auth/change-password` |
| Each browser tab keeps its own token (`sessionStorage`); closing the tab ends that session | `frontend/src/api/session.js` |

## 4. Threat detection & digital forensics

| Control | Where |
|---|---|
| Every sign-in, failed sign-in, blocked attempt, sign-up, password change and "signed out everywhere" is recorded with time, IP address and browser | `security_events` table, `services/security_events.py` |
| Brute-force detection counts recent failures in the database, so a server restart does not reset it | `services/security_events.py` |
| **Security page** (Dashboard → Security): the user's own recent activity, a warning when there were failed attempts in the last 7 days, change password, sign out everywhere | `frontend/src/pages/SecurityPage.jsx` |
| Project audit trail: every task change, assignment (including when an admin overrode the AI's suggestion and whom the AI had suggested), plan application and decision is in the activity log | `activity_log` table |
| `Server-Timing` header on every API response (time in code vs. database, number of queries) to investigate slow or unusual requests | `app/middleware.py` |

## Known limits (said honestly)

- Rate limits for the AI endpoints live in memory: a restart of the free server resets them (sign-in limits do not, they are in the database).
- The IP address comes from the proxy's `X-Forwarded-For`; a client can fake it, which only lets it avoid the *per-network* limit – the per-email limit still applies.
- There is no two-factor authentication and no email-based password reset (no free email service is used).
- The WebSocket token is passed in the URL (browsers cannot set headers on WebSockets); it is short-lived and revocable.
