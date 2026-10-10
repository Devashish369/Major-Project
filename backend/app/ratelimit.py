"""
ratelimit.py – per-user limits on the AI endpoints, so one account (or a stolen token) cannot
use up the FREE Groq / Gemini quota for everybody.

Sliding window kept in memory: fine for the single free Render instance (a restart simply
starts the windows again).  Raises HTTP 429 with a Retry-After header.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.deps import get_current_user

_lock = threading.Lock()
_hits: dict[tuple[str, int], deque] = defaultdict(deque)


def limit(name: str, max_calls: int, per_seconds: int):
    """FastAPI dependency: at most `max_calls` calls of `name` per user per `per_seconds`."""
    def dependency(current_user=Depends(get_current_user)):
        now = time.monotonic()
        with _lock:
            q = _hits[(name, current_user.id)]
            while q and now - q[0] >= per_seconds:
                q.popleft()
            if len(q) >= max_calls:
                wait = int(per_seconds - (now - q[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many AI requests. Please wait {wait} s (limit {max_calls} per "
                           f"{per_seconds // 60} min, to keep the free AI quota available).",
                    headers={"Retry-After": str(wait)},
                )
            q.append(now)
        return current_user
    return dependency


def reset() -> None:
    """Tests only."""
    with _lock:
        _hits.clear()
