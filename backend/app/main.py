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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base


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


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch any unhandled exception and return it in the standard error envelope.
    HTTPException is NOT caught here – FastAPI handles it before this handler.
    """
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": str(exc), "errors": []},
    )


# ── Register routers ──────────────────────────────────────────────────────────
# Import AFTER ok/err are defined to avoid circular import issues.
from app.routers import auth as auth_router        # noqa: E402
from app.routers import projects as projects_router  # noqa: E402
from app.routers import members as members_router    # noqa: E402
from app.routers import tasks as tasks_router        # noqa: E402

app.include_router(auth_router.router,     prefix="/api/v1")
app.include_router(projects_router.router, prefix="/api/v1")
app.include_router(members_router.router,  prefix="/api/v1")
app.include_router(tasks_router.router,    prefix="/api/v1")

# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["health"])
def health_check():
    """
    GET /api/v1/health  →  {"success": true, "data": {"status": "ok"}, "message": "OK"}
    M0 done-when test; also used by frontend to check connectivity.
    """
    return ok(data={"status": "ok"})
