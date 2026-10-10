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
import threading

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base


logger = logging.getLogger(__name__)


def _warm_models() -> None:
    """Best effort: a failure here only means the first request loads the model itself."""
    try:
        from app.services import estimator, risk
        risk._load()
        estimator._load_model()
        logger.info("ML models warmed up")
    except Exception:
        logger.exception("Model warm-up failed (models will load on first use)")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup. Clean shutdown on exit."""
    import app.models  # noqa: F401 – registers all ORM models with Base.metadata
    Base.metadata.create_all(bind=engine)
    from app.migrations import upgrade
    upgrade(engine)   # add columns that create_all cannot add to existing tables
    # Load the ML models in the background NOW, so the first person to open Analytics does not
    # wait for scikit-learn to import and the models to unpickle (several seconds on a free server).
    threading.Thread(target=_warm_models, daemon=True, name="warm-models").start()
    yield   # application runs here
    # (no teardown needed for SQLite; add connection-pool cleanup here for Postgres)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="IntelliPM API",
    version="0.1.0",
    description="AI-assisted project management – IntelliPM backend",
    lifespan=lifespan,   # modern replacement for @app.on_event("startup")
)

# Security headers, 1 MB body limit, Server-Timing (app/middleware.py)
from app.middleware import SecurityAndTimingMiddleware  # noqa: E402
app.add_middleware(SecurityAndTimingMiddleware)

# Compress JSON responses over 1 KB (a 30-task list shrinks ~5x): less data over the internet
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Server-Timing", "Retry-After"],
    # Browsers ask permission (an extra "preflight" round trip) before each cross-origin call that
    # carries a token; let them remember the answer for 2 h (Chrome's maximum) instead of 10 min.
    max_age=7200,
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
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"),
         "message": e["msg"].removeprefix("Value error, ")}
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
from app.routers import report as report_router  # noqa: E402
from app.routers import sprints as sprints_router  # noqa: E402
from app.routers import ws as ws_router  # noqa: E402

app.include_router(auth_router.router,       prefix="/api/v1")
app.include_router(projects_router.router,   prefix="/api/v1")
app.include_router(members_router.router,    prefix="/api/v1")
app.include_router(tasks_router.router,      prefix="/api/v1")
app.include_router(ai_router.router,         prefix="/api/v1")
app.include_router(assign_router.router,     prefix="/api/v1")
app.include_router(analytics_router.router,  prefix="/api/v1")
app.include_router(decisions_router.router,  prefix="/api/v1")
app.include_router(report_router.router,     prefix="/api/v1")
app.include_router(sprints_router.router,    prefix="/api/v1")
app.include_router(ws_router.router)   # WS /ws/projects/{id} (no /api/v1 prefix, per spec)

# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["health"])
def health_check():
    """
    GET /api/v1/health  →  {"success": true, "data": {"status": "ok"}, "message": "OK"}
    M0 done-when test; also used by frontend to check connectivity.
    """
    return ok(data={"status": "ok"})


_db_probe = {"at": 0.0, "data": None}


@app.get("/api/v1/health/db", tags=["health"])
def health_db():
    """
    Database round-trip time in ms (median of 3 "SELECT 1").  Shows whether the API and the
    database are in the same region (≈1–3 ms) or not (≈30–80 ms).  Measured at most once a
    minute; NOT for uptime pings (it wakes the database – use /api/v1/health for those).
    """
    import time as _time
    from sqlalchemy import text as _text
    now = _time.monotonic()
    if _db_probe["data"] is None or now - _db_probe["at"] > 60:
        times = []
        with engine.connect() as conn:
            conn.execute(_text("SELECT 1"))          # first one may include waking up / connecting
            for _ in range(3):
                t0 = _time.perf_counter()
                conn.execute(_text("SELECT 1"))
                times.append((_time.perf_counter() - t0) * 1000)
        _db_probe.update(at=now, data={"db_round_trip_ms": round(sorted(times)[1], 1),
                                       "database": "sqlite" if settings.is_sqlite else "postgresql"})
    return ok(data=_db_probe["data"])
