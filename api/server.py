"""
Hardened FastAPI Backend for SplitLang (React FE + MySQL 8.x/9.x).

Enforces all 20 security controls:
  1. Hide API keys             (server-only .env via module/config.py)
  2. Purge Git secrets         (.gitignore + scripts/security_check.py)
  3. Least-privilege DB user   (splitlang_app, zero DB access from React FE)
  4. Row-level security        (owner_user_id on every query/table)
  5. Encrypt sensitive data    (Fernet AES+HMAC on sensitive columns)
  6. Server-side auth          (HttpOnly session cookie verified against DB)
  7. Lock record access        (IDOR guard verifying group.owner_user_id == user.id)
  8. Block field tampering     (Pydantic extra="forbid" on all request schemas)
  9. Secure session cookies    (HttpOnly, SameSite=Lax, Secure, hashed token, CSRF header)
 10. Hash passwords            (Argon2id + strong password policy)
 11. Rate limit login          (SlidingWindowRateLimiter returning 429 + Retry-After)
 12. Bot protection            (Honeypot + HMAC-signed single-use challenge)
 13. Parameterize queries      (100% %s / ? parameterized SQL)
 14. Validate all input        (Pydantic bounds + ANTLR4 grammar + semantic checks)
 15. Escape user content       (React JSX auto-escape + control-char stripping)
 16. Restrict file uploads     (.split only, <=64KB, UTF-8, no null bytes, in-memory)
 17. Trim API responses        (UserPublic & trimmed dashboard payloads, no stack traces)
 18. Security headers          (CSP, nosniff, DENY, Referrer-Policy, Permissions-Policy)
 19. Force HTTPS               (FORCE_HTTPS redirect + HSTS)
 20. Scan dependencies         (scripts/security_check.py + npm audit)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.middleware import SecurityMiddleware
from api.schemas import (
    AuthResponse,
    DemoRequest,
    ExecuteRequest,
    LoginRequest,
    RegisterRequest,
    UploadResponse,
    UserPublic,
)
from controller.Response import SplitLangInterpreter
from module.config import Settings, load_settings
from module.Database import Database
from module.security import (
    BotProtector,
    SlidingWindowRateLimiter,
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_split_upload,
    verify_csrf_token,
    verify_password,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REACT_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

SESSION_COOKIE_NAME = "splitlang_session"

DEMO_FILES = {
    "dinner": EXAMPLES_DIR / "dinner_demo.split",
    "trip": EXAMPLES_DIR / "usd_trip_demo.split",
}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
        docs_url=None,      # Disable Swagger/OpenAPI surface in hardened mode
        redoc_url=None,
    )
    app.state.db = db
    app.state.settings = cfg
    app.state.active_groups: dict[int, int] = {}  # user_id -> active_group_id
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

    # ------------------------------------------------------------------
    # Server-Side Auth & CSRF Dependencies (Controls #6, #7, #9)
    # ------------------------------------------------------------------

    def get_current_session(request: Request) -> dict[str, Any]:
        raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        if not raw_cookie:
            raise HTTPException(status_code=401, detail="Authentication required.")
        session = db.get_session_by_token_hash(hash_session_token(raw_cookie))
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid.")
        return session

    def require_csrf(request: Request, session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
        provided = request.headers.get("x-csrf-token")
        if not verify_csrf_token(session["csrf_token"], provided):
            raise HTTPException(status_code=403, detail="Invalid or missing CSRF token.")
        return session

    def _set_session_cookie(response: Response, raw_token: str) -> None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=raw_token,
            httponly=True,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
            max_age=cfg.session_ttl_hours * 3600,
            path="/",
        )

    def _get_user_interpreter(user_id: int, requested_group_id: int | None = None) -> SplitLangInterpreter:
        gid = requested_group_id or app.state.active_groups.get(user_id)
        if gid is not None:
            # Control #7: Verify ownership before attaching to group
            try:
                db.get_group_by_id(gid, owner_user_id=user_id)
            except PermissionError:
                if requested_group_id is not None:
                    raise HTTPException(status_code=403, detail="Access denied to requested group.")
                gid = None
        interp = SplitLangInterpreter(db=db, owner_user_id=user_id, active_group_id=gid)
        app.state.active_groups[user_id] = interp.ctx.active_group_id
        return interp

    # ------------------------------------------------------------------
    # Public Health & Auth Endpoints (Controls #6, #9, #10, #11, #12)
    # ------------------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "backend": db.backend}

    @app.get("/api/auth/challenge")
    def auth_challenge() -> dict[str, Any]:
        return app.state.bot.issue_challenge()

    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(req: RegisterRequest, request: Request, response: Response):
        ip = _client_ip(request)
        allowed, retry_after = app.state.login_limiter.check(f"reg:{ip}")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many registration attempts. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        ok_bot, bot_msg = app.state.bot.verify(
            honeypot=req.website,
            challenge_token=req.challenge_token,
            answer=req.challenge_answer,
        )
        if not ok_bot:
            raise HTTPException(status_code=400, detail=bot_msg)

        if db.get_user_by_username(req.username):
            raise HTTPException(status_code=409, detail="Username is already taken.")

        pw_hash = hash_password(req.password)
        user = db.create_user(username=req.username, email=req.email, password_hash=pw_hash)
        default_grp = db.ensure_group("Default", currency="VND", owner_user_id=user["id"])
        app.state.active_groups[user["id"]] = default_grp["id"]

        raw_token = generate_session_token()
        csrf = generate_csrf_token()
        db.create_session(
            user_id=user["id"],
            token_hash=hash_session_token(raw_token),
            csrf_token=csrf,
            ttl_hours=cfg.session_ttl_hours,
        )
        _set_session_cookie(response, raw_token)
        return AuthResponse(
            user=UserPublic(username=user["username"], email=user["email"], role=user["role"]),
            csrf_token=csrf,
        )

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(req: LoginRequest, request: Request, response: Response):
        ip = _client_ip(request)
        rate_key = f"login:{ip}:{req.username.strip().lower()}"
        allowed, retry_after = app.state.login_limiter.check(rate_key, record=False)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        ok_bot, bot_msg = app.state.bot.verify(
            honeypot=req.website,
            challenge_token=req.challenge_token,
            answer=req.challenge_answer,
        )
        if not ok_bot:
            app.state.login_limiter.check(rate_key, record=True)
            raise HTTPException(status_code=400, detail=bot_msg)

        user_row = db.get_user_by_username(req.username.strip())
        if not user_row or not verify_password(user_row["password_hash"], req.password):
            app.state.login_limiter.check(rate_key, record=True)
            # Uniform generic message to prevent user enumeration
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        app.state.login_limiter.reset(rate_key)
        raw_token = generate_session_token()
        csrf = generate_csrf_token()
        db.create_session(
            user_id=user_row["id"],
            token_hash=hash_session_token(raw_token),
            csrf_token=csrf,
            ttl_hours=cfg.session_ttl_hours,
        )
        _set_session_cookie(response, raw_token)
        return AuthResponse(
            user=UserPublic(
                username=user_row["username"],
                email=user_row["email"],
                role=user_row["role"],
            ),
            csrf_token=csrf,
        )

    @app.get("/api/auth/me", response_model=AuthResponse)
    def auth_me(session: dict[str, Any] = Depends(get_current_session)):
        user = db.get_user_by_id(session["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="Account not found.")
        return AuthResponse(
            user=UserPublic(username=user["username"], email=user["email"], role=user["role"]),
            csrf_token=session["csrf_token"],
        )

    @app.post("/api/auth/logout")
    def logout(
        request: Request,
        response: Response,
        _session: dict[str, Any] = Depends(require_csrf),
    ) -> dict[str, bool]:
        raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        if raw_cookie:
            db.delete_session(hash_session_token(raw_cookie))
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return {"ok": True}

    # ------------------------------------------------------------------
    # Authenticated & Row-Level-Secured DSL Endpoints
    # ------------------------------------------------------------------

    @app.get("/api/state")
    def get_state(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
        interp = _get_user_interpreter(session["user_id"])
        return interp.get_dashboard_state()

    @app.post("/api/groups/{group_id}/select")
    def select_group(
        group_id: int,
        session: dict[str, Any] = Depends(require_csrf),
    ) -> dict[str, Any]:
        interp = _get_user_interpreter(session["user_id"], requested_group_id=group_id)
        return interp.get_dashboard_state()

    @app.post("/api/execute")
    def execute_code(
        req: ExecuteRequest,
        request: Request,
        session: dict[str, Any] = Depends(require_csrf),
    ) -> dict[str, Any]:
        allowed, retry_after = app.state.api_limiter.check(f"exec:{session['user_id']}:{_client_ip(request)}")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Slow down.",
                headers={"Retry-After": str(retry_after)},
            )
        interp = _get_user_interpreter(session["user_id"], requested_group_id=req.group_id)
        result = interp.execute(req.code)
        app.state.active_groups[session["user_id"]] = interp.ctx.active_group_id
        return {
            "execution": result,
            "state": interp.get_dashboard_state(),
        }

    @app.post("/api/demo")
    def run_demo(
        req: DemoRequest,
        session: dict[str, Any] = Depends(require_csrf),
    ) -> dict[str, Any]:
        demo_path = DEMO_FILES.get(req.name)
        if not demo_path or not demo_path.is_file():
            raise HTTPException(status_code=404, detail="Demo not found.")
        code = demo_path.read_text(encoding="utf-8")
        interp = _get_user_interpreter(session["user_id"])
        result = interp.execute(code)
        app.state.active_groups[session["user_id"]] = interp.ctx.active_group_id
        return {
            "code": code,
            "execution": result,
            "state": interp.get_dashboard_state(),
        }

    # Control #16: Restricted in-memory .split file upload
    @app.post("/api/upload", response_model=UploadResponse)
    async def upload_split_file(
        file: UploadFile = File(...),
        _session: dict[str, Any] = Depends(require_csrf),
    ):
        raw_bytes = await file.read(65537)  # Read at most 64KB + 1 byte
        try:
            clean_name, decoded = validate_split_upload(file.filename, raw_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UploadResponse(filename=clean_name, code=decoded, size_bytes=len(raw_bytes))

    # ------------------------------------------------------------------
    # Serve Built React SPA (frontend/dist)
    # ------------------------------------------------------------------

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
