"""
Public Health & Authentication Router (/api/health, /api/auth/*).

Enforces Controls #6, #9, #10, #11, #12, #17.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.core.dependencies import (
    SESSION_COOKIE_NAME,
    client_ip,
    get_current_session,
    require_csrf,
    set_session_cookie,
)
from backend.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from backend.schemas.api_schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublic

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "backend": request.app.state.db.backend}


@router.get("/auth/challenge")
def auth_challenge(request: Request) -> dict[str, Any]:
    return request.app.state.bot.issue_challenge()


@router.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest, request: Request, response: Response):
    state = request.app.state
    db = state.db
    cfg = state.settings
    ip = client_ip(request)

    allowed, retry_after = state.login_limiter.check(f"reg:{ip}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many registration attempts. Retry after {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    ok_bot, bot_msg = state.bot.verify(
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
    state.active_groups[user["id"]] = default_grp["id"]

    raw_token = generate_session_token()
    csrf = generate_csrf_token()
    db.create_session(
        user_id=user["id"],
        token_hash=hash_session_token(raw_token),
        csrf_token=csrf,
        ttl_hours=cfg.session_ttl_hours,
    )
    set_session_cookie(request, response, raw_token)
    return AuthResponse(
        user=UserPublic(username=user["username"], email=user["email"], role=user["role"]),
        csrf_token=csrf,
    )


@router.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, response: Response):
    state = request.app.state
    db = state.db
    cfg = state.settings
    ip = client_ip(request)
    rate_key = f"login:{ip}:{req.username.strip().lower()}"

    allowed, retry_after = state.login_limiter.check(rate_key, record=False)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    ok_bot, bot_msg = state.bot.verify(
        honeypot=req.website,
        challenge_token=req.challenge_token,
        answer=req.challenge_answer,
    )
    if not ok_bot:
        state.login_limiter.check(rate_key, record=True)
        raise HTTPException(status_code=400, detail=bot_msg)

    user_row = db.get_user_by_username(req.username.strip())
    if not user_row or not verify_password(user_row["password_hash"], req.password):
        state.login_limiter.check(rate_key, record=True)
        # Uniform generic message to prevent user enumeration
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    state.login_limiter.reset(rate_key)
    raw_token = generate_session_token()
    csrf = generate_csrf_token()
    db.create_session(
        user_id=user_row["id"],
        token_hash=hash_session_token(raw_token),
        csrf_token=csrf,
        ttl_hours=cfg.session_ttl_hours,
    )
    set_session_cookie(request, response, raw_token)
    return AuthResponse(
        user=UserPublic(
            username=user_row["username"],
            email=user_row["email"],
            role=user_row["role"],
        ),
        csrf_token=csrf,
    )


@router.get("/auth/me", response_model=AuthResponse)
def auth_me(request: Request, session: dict[str, Any] = Depends(get_current_session)):
    user = request.app.state.db.get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    return AuthResponse(
        user=UserPublic(username=user["username"], email=user["email"], role=user["role"]),
        csrf_token=session["csrf_token"],
    )


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    _session: dict[str, Any] = Depends(require_csrf),
) -> dict[str, bool]:
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if raw_cookie:
        request.app.state.db.delete_session(hash_session_token(raw_cookie))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}
