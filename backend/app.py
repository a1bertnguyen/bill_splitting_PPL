"""
Hardened FastAPI Application Factory for SplitLang v2.0 (Enterprise Layered Architecture).

Layers:
  - backend/routers/       : Modular HTTP endpoints (auth, workspace/DSL)
  - backend/middleware/    : Security headers & HTTPS enforcement
  - backend/schemas/       : Strict Pydantic v2 request/response models
  - backend/core/          : Settings, security primitives, auth/CSRF dependencies
  - backend/compiler/      : ANTLR 4.9.2 grammar/generated files, Typed AST, Visitor
  - backend/services/      : SplitLang Interpreter & Deterministic Financial Math
  - backend/repositories/  : MySQL 9.4 / SQLite persistence with Fernet AES & RLS
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import Settings, load_settings
from backend.core.security import BotProtector, SlidingWindowRateLimiter
from backend.middleware.security_headers import SecurityMiddleware
from backend.repositories.database import Database
from backend.routers.auth import router as auth_router
from backend.routers.workspace import router as workspace_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REACT_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


def create_app(
    *,
    db_path: str | Path | None = None,
    settings: Settings | None = None,
    min_bot_solve_seconds: float = 0.0,
) -> FastAPI:
    cfg = settings or load_settings(allow_ephemeral_keys=True)
    db = Database(db_path=db_path, settings=cfg)

    app = FastAPI(
        title="SplitLang — Secure Bill-Splitting DSL API",
        version="2.0.0",
        docs_url=None,  # Disable Swagger/OpenAPI surface in hardened mode
        redoc_url=None,
    )
    app.state.db = db
    app.state.settings = cfg
    app.state.active_groups: dict[int, int] = {}         # user_id -> active_group_id
    app.state.user_envs: dict[int, dict[str, Any]] = {}   # user_id -> Symbol Table variables
    app.state.user_rules: dict[int, dict[str, Any]] = {}  # user_id -> Symbol Table split rules
    app.state.login_limiter = SlidingWindowRateLimiter(
        max_requests=cfg.login_rate_limit_max,
        window_seconds=cfg.login_rate_limit_window_sec,
    )
    app.state.api_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60)
    app.state.bot = BotProtector(cfg.secret_key, min_solve_seconds=min_bot_solve_seconds)

    # Control #18 & #19: Security Headers + Force HTTPS
    app.add_middleware(SecurityMiddleware, settings=cfg)

    # Strict CORS allowlist (never "*" with credentials)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    # Control #17: Never leak raw stack traces or SQL exceptions
    @app.exception_handler(Exception)
    async def safe_exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, PermissionError):
            return JSONResponse(status_code=403, content={"detail": "Access denied."})
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    # Register Modular API Routers
    app.include_router(auth_router)
    app.include_router(workspace_router)

    # Serve Built React SPA (frontend/dist)
    if REACT_DIST_DIR.is_dir():
        assets_dir = REACT_DIST_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        def serve_react_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API endpoint not found.")
            candidate = (REACT_DIST_DIR / full_path).resolve()
            if full_path and candidate.is_file() and REACT_DIST_DIR.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(REACT_DIST_DIR / "index.html")

    return app


def get_default_app() -> FastAPI:
    return create_app()
