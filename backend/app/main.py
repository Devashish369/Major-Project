"""
main.py – FastAPI application entry point for IntelliPM.

Responsibilities:
  - Create the app with metadata (title, version, docs URL).
  - Add CORS middleware (origins from config).
  - Register the global exception handler that wraps all errors in the
    response envelope defined in section 7 of PROJECT_SPEC.md.
  - Register routers.
  - Create DB tables on startup via Base.metadata.create_all.

Response envelope (section 7):
  Success: { "success": true,  "data": <payload>, "message": "<text>" }
  Error:   { "success": false, "message": "<text>", "errors": [] }
"""

from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base


logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup. Clean shutdown on exit."""
    import app.models  # noqa: F401 – registers all ORM models with Base.metadata
    Base.metadata.create_all(bind=engine)
    yield   # application runs here
    # (no teardown needed for SQLite; add connection-pool cleanup here for Postgres)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="IntelliPM API",
    version="0.1.0",
    description="AI-assisted project management – IntelliPM backend",
    lifespan=lifespan,   # modern replacement for @app.on_event("startup")
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Response envelope helpers ─────────────────────────────────────────────────
def ok(data=None, message: str = "OK") -> dict:
    """Build a success envelope. Routers return this dict directly."""
    return {"success": True, "data": data, "message": message}


def err(message: str, errors: list = None, status: int = 400):
    """Build an error JSONResponse. Routers can return this for error cases."""
    return JSONResponse(
        status_code=status,
        content={"success": False, "message": message, "errors": errors or []},
    )


# ── Error handlers: every error uses the spec §7 envelope ─────────────────────
# {"success": false, "message": str, "errors": [...]}.  We also keep FastAPI's usual
# "detail" key so the frontend (which reads response.data.detail) and old clients keep working.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """401/403/404/409/503 ... raised with HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
        content={"success": False, "message": str(exc.detail), "errors": [], "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422: the request body / params did not match the schema."""
    errors = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
        for e in exc.errors()
    ]
    summary = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors)
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": f"Validation failed. {summary}"[:500],
            "errors": errors,
            "detail": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Any unhandled exception -> 500.  The real error goes to the server log only;
    clients get a generic message so internals (SQL, paths) are never leaked.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error.", "errors": []},
    )


# ── Register routers ──────────────────────────────────────────────────────────
# Import AFTER ok/err are defined to avoid circular import issues.
from app.routers import auth as auth_router        # noqa: E402
from app.routers import projects as projects_router  # noqa: E402
from app.routers import members as members_router    # noqa: E402
from app.routers import tasks as tasks_router        # noqa: E402
from app.routers import ai as ai_router              # noqa: E402
from app.routers import assignments as assign_router  # noqa: E402
from app.routers import analytics as analytics_router  # noqa: E402
from app.routers import decisions as decisions_router  # noqa: E402
from app.routers import ws as ws_router  # noqa: E402

app.include_router(auth_router.router,       prefix="/api/v1")
app.include_router(projects_router.router,   prefix="/api/v1")
app.include_router(members_router.router,    prefix="/api/v1")
app.include_router(tasks_router.router,      prefix="/api/v1")
app.include_router(ai_router.router,         prefix="/api/v1")
app.include_router(assign_router.router,     prefix="/api/v1")
app.include_router(analytics_router.router,  prefix="/api/v1")
app.include_router(decisions_router.router,  prefix="/api/v1")
app.include_router(ws_router.router)   # WS /ws/projects/{id} (no /api/v1 prefix, per spec)

# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["health"])
def health_check():
    """
    GET /api/v1/health  →  {"success": true, "data": {"status": "ok"}, "message": "OK"}
    M0 done-when test; also used by frontend to check connectivity.
    """
    return ok(data={"status": "ok"})
