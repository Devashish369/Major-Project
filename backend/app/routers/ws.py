"""
routers/ws.py – live project updates over WebSocket (spec §7 Realtime, M13).

    WS /ws/projects/{id}?token=<JWT>

  * The browser WebSocket API cannot send an Authorization header, so (as the spec says)
    the JWT travels in the query string.  It is verified exactly like a REST token and the
    user must be a member of the project; otherwise the handshake is refused (HTTP 403).
  * The server pushes {"type": "task_created" | "task_updated" | "task_deleted", "task": {...}}.
  * The client may send the text "ping"; the server answers {"type": "pong"}.  Clients use
    this as a keep-alive because hosting proxies close idle sockets after about a minute.
  * Clients never send changes over the socket; edits still go through the normal REST API.
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProjectMember, User
from app.security import decode_claims
from app.services.realtime import manager

router = APIRouter(tags=["realtime"])

WS_POLICY_VIOLATION = 1008   # refused: bad token / not a member
WS_TRY_AGAIN_LATER = 1013    # refused: room is full


def _is_member(db: Session, token: str, project_id: int) -> bool:
    claims = decode_claims(token) if token else None
    if claims is None:
        return False
    user_id, token_version = claims
    user = db.get(User, user_id)
    if user is None or user.token_version != token_version:   # revoked token
        return False
    return db.execute(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    ).first() is not None


@router.websocket("/ws/projects/{project_id}")
async def project_socket(
    websocket: WebSocket,
    project_id: int,
    token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    allowed = await run_in_threadpool(_is_member, db, token, project_id)
    db.close()                      # release the DB connection: a socket can stay open for hours
    if not allowed:
        await websocket.close(code=WS_POLICY_VIOLATION)
        return
    if manager.is_full(project_id):
        await websocket.close(code=WS_TRY_AGAIN_LATER)
        return

    await manager.connect(project_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "project_id": project_id})
        while True:
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:               # any other socket error: just drop this client
        pass
    finally:
        manager.disconnect(project_id, websocket)
