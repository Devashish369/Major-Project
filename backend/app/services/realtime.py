"""
services/realtime.py – WebSocket rooms + event publishing (M13).

How it works (viva-ready):
  * One "room" per project: the set of WebSocket connections currently watching it.
  * The task endpoints are ordinary synchronous functions that FastAPI runs in a
    thread pool, but sending on a WebSocket is async and must happen on the server's
    event loop.  `publish()` therefore hands the send over with
    `asyncio.run_coroutine_threadsafe(...)`, which is the thread-safe way to do that.
  * Events are published AFTER the database commit, so a client never hears about a
    change that was rolled back.
  * If nobody is watching a project, publish() returns immediately (no queries, no cost).
  * If the socket layer fails for any reason it must never break the REST call, so every
    failure here is swallowed and logged.

Limitation: rooms live in this process's memory, so real-time updates reach only clients
connected to the same server process (fine for one Render instance; scaling to several
instances would need a message broker such as Redis).
"""

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_PROJECT = 50


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── connection lifecycle (called from the async WebSocket endpoint) ──────
    def is_full(self, project_id: int) -> bool:
        return len(self._rooms[project_id]) >= MAX_CONNECTIONS_PER_PROJECT

    async def connect(self, project_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._loop = asyncio.get_running_loop()     # remember the loop publish() must use
        self._rooms[project_id].add(ws)

    def disconnect(self, project_id: int, ws: WebSocket) -> None:
        self._rooms[project_id].discard(ws)
        if not self._rooms[project_id]:
            self._rooms.pop(project_id, None)

    def has_listeners(self, project_id: int) -> bool:
        return bool(self._rooms.get(project_id))

    # ── publishing ───────────────────────────────────────────────────────────
    async def _send_all(self, project_id: int, message: dict) -> None:
        for ws in list(self._rooms.get(project_id, ())):
            try:
                await ws.send_json(message)
            except Exception:                        # closed / broken socket: drop it
                self.disconnect(project_id, ws)

    def publish(self, project_id: int, message: dict) -> None:
        """Thread-safe, never raises."""
        try:
            if not self.has_listeners(project_id) or self._loop is None or self._loop.is_closed():
                return
            asyncio.run_coroutine_threadsafe(
                self._send_all(project_id, jsonable_encoder(message)), self._loop
            )
        except Exception:
            logger.exception("Realtime publish failed (ignored)")


manager = ConnectionManager()


# ── Helpers used by the routers ───────────────────────────────────────────────

def emit_tasks(db: Session, project_id: int, event_type: str, task_ids: list[int], actor_id: Optional[int]) -> None:
    """
    Publish `event_type` ("task_created" | "task_updated") for each task id, using the same
    JSON shape as GET /tasks (including the dependency list).  Call after commit.
    """
    if not task_ids or not manager.has_listeners(project_id):
        return
    try:
        from app.models import Task
        from app.routers.tasks import _task_out          # lazy import: avoids a circular import

        rows = db.execute(select(Task).where(Task.id.in_(task_ids))).scalars().all()
        for t in rows:
            manager.publish(project_id, {"type": event_type, "task": _task_out(t, db), "actor_id": actor_id})
    except Exception:
        logger.exception("Realtime emit failed (ignored)")


def emit_task_deleted(project_id: int, task_id: int, actor_id: Optional[int]) -> None:
    manager.publish(project_id, {
        "type": "task_deleted", "task": {"id": task_id, "project_id": project_id}, "actor_id": actor_id,
    })
