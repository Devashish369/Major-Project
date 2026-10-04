"""
main.py – FastAPI application entry point for IntelliPM.

Responsibilities:
  - Create the app with metadata (title, version, docs URL).
  - Add CORS middleware (origins from config).
  - Register the global exception handler that wraps all errors in the
    response envelope defined in section 7 of PROJECT_SPEC.md.
  - Register routers (only /health for M0; others added in later modules).
  - Create DB tables on startup via Base.metadata.create_all.

Response envelope (section 7):
  Success: { "success": true,  "data": <payload>, "message": "<text>" }
  Error:   { "success": false, "message": "<text>", "errors": [] }
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="IntelliPM API",
    version="0.1.0",
    description="AI-assisted project management – IntelliPM backend",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,   # e.g. ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch any unhandled exception and return it in the standard error envelope.
    This prevents raw Python tracebacks from leaking to API clients.
    """
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": str(exc),
            "errors": [],
        },
    )

# ── Startup: create tables ────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """
    Create all SQLAlchemy tables if they don't exist yet.
    We import models here (even though models.py is empty in M0) so that
    any models defined later are registered with Base.metadata before
    create_all is called.
    """
    # Import models so they register with Base (will be populated in M1+)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


# ── Response envelope helpers ─────────────────────────────────────────────────
def ok(data=None, message: str = "OK") -> dict:
    """Build a success envelope. Routers return this dict directly."""
    return {"success": True, "data": data, "message": message}


def err(message: str, errors: list = None, status: int = 400):
    """Build an error envelope. Routers raise HTTPException or return this."""
    return JSONResponse(
        status_code=status,
        content={"success": False, "message": message, "errors": errors or []},
    )


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["health"])
def health_check():
    """
    GET /api/v1/health

    Returns {"success": true, "data": {"status": "ok"}, "message": "OK"}.
    Used by the frontend to verify the backend is reachable (M0 done-when test).
    """
    return ok(data={"status": "ok"})
