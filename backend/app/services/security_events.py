"""
services/security_events.py – sign-in audit trail and brute-force protection.

Threat detection: every sign-in attempt is recorded (security_events table) with time, IP and
browser.  Before checking a password we count the recent FAILED attempts:
    ≥ 5 failures for this email from this IP in 15 min   → blocked (stops password guessing)
    ≥ 20 failures for this email from any IP in 15 min   → blocked (stops attacks that rotate IPs)
    ≥ 50 failures from this IP for any email in 15 min   → blocked (stops trying many accounts)
A blocked attempt gets HTTP 429 with Retry-After and is itself recorded.  Counting in the
database (not in memory) means a restart of the free server does not reset the protection.
The block is per email+IP first, so a stranger cannot lock you out from your own network by
mistyping your email five times; only a large attack reaches the per-email limit.

Digital forensics: the user can see their own recent events (Security page) – successful and
failed sign-ins, password changes and "signed out everywhere" – and spot activity that was not them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SecurityEvent

WINDOW = timedelta(minutes=15)
MAX_PER_EMAIL_IP = 5
MAX_PER_EMAIL = 20
MAX_PER_IP = 50          # generous: a classroom shares one public IP
REGISTER_WINDOW = timedelta(hours=1)
MAX_REGISTER_PER_IP = settings.REGISTER_LIMIT_PER_HOUR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def client_ip(request: Request) -> str:
    """
    The visitor's address.  Render's proxy puts it first in X-Forwarded-For.  A client could
    send a fake header, which only lets it dodge the per-IP limit – the per-email limit still
    applies – and the value is only shown as information, never trusted for access.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return ip[:64] or "unknown"


def record(db: Session, request: Request, event: str, *, user_id: Optional[int] = None,
           email: Optional[str] = None) -> None:
    """Add an event to the session (the caller commits)."""
    db.add(SecurityEvent(
        created_at=_now(), user_id=user_id, email=(email or "").lower()[:320] or None, event=event,
        ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300] or None,
    ))


def login_block_seconds(db: Session, email: str, ip: str) -> int:
    """0 if a login may be tried now, else how many seconds until it may (one query)."""
    since = _now() - WINDOW
    email = email.lower()
    failed = SecurityEvent.event == "login_failed"
    same_email = SecurityEvent.email == email
    same_ip = SecurityEvent.ip == ip
    row = db.execute(
        select(
            func.sum(case((same_email & same_ip, 1), else_=0)),
            func.sum(case((same_email, 1), else_=0)),
            func.sum(case((same_ip, 1), else_=0)),
            func.min(SecurityEvent.created_at),
        ).where(failed, SecurityEvent.created_at >= since, or_(same_email, same_ip))
    ).one()
    per_pair, per_email, per_ip, oldest = (row[0] or 0), (row[1] or 0), (row[2] or 0), row[3]
    if per_pair < MAX_PER_EMAIL_IP and per_email < MAX_PER_EMAIL and per_ip < MAX_PER_IP:
        return 0
    if oldest is None:
        return int(WINDOW.total_seconds())
    if oldest.tzinfo is None:                     # SQLite returns naive UTC datetimes
        oldest = oldest.replace(tzinfo=timezone.utc)
    return max(1, int((oldest + WINDOW - _now()).total_seconds()))


def register_blocked(db: Session, ip: str) -> bool:
    """True when this IP created too many accounts in the last hour (stops sign-up spam)."""
    n = db.execute(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.event == "register", SecurityEvent.ip == ip,
            SecurityEvent.created_at >= _now() - REGISTER_WINDOW,
        )
    ).scalar_one()
    return n >= MAX_REGISTER_PER_IP


def recent_for_user(db: Session, user_id: int, email: str, limit: int = 25) -> list[SecurityEvent]:
    return db.execute(
        select(SecurityEvent)
        .where(or_(SecurityEvent.user_id == user_id, SecurityEvent.email == email.lower()))
        .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
        .limit(limit)
    ).scalars().all()
