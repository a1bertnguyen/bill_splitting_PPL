"""
Shared FastAPI Dependencies for Server-Side Auth, CSRF, and Row-Level Isolation.

Enforces Controls #6 (Server-side auth), #7 (Lock record access / IDOR guard),
and #9 (Secure HttpOnly session cookie + CSRF header verification).
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, Response

from backend.core.security import hash_session_token, verify_csrf_token
from backend.services.interpreter import SplitLangInterpreter

SESSION_COOKIE_NAME = "splitlang_session"


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def set_session_cookie(request: Request, response: Response, raw_token: str) -> None:
    cfg = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,
        max_age=cfg.session_ttl_hours * 3600,
        path="/",
    )


def get_current_session(request: Request) -> dict[str, Any]:
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Authentication required.")
    db = request.app.state.db
    session = db.get_session_by_token_hash(hash_session_token(raw_cookie))
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
    return session


def require_csrf(
    request: Request,
    session: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    provided = request.headers.get("x-csrf-token")
    if not verify_csrf_token(session["csrf_token"], provided):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token.")
    return session


def get_user_interpreter(
    request: Request,
    user_id: int,
    requested_group_id: int | None = None,
) -> SplitLangInterpreter:
    app_state = request.app.state
    db = app_state.db
    gid = requested_group_id or app_state.active_groups.get(user_id)
    if gid is not None:
        # Control #7: Verify ownership before attaching to group
        try:
            db.get_group_by_id(gid, owner_user_id=user_id)
        except PermissionError:
            if requested_group_id is not None:
                raise HTTPException(status_code=403, detail="Access denied to requested group.")
            gid = None
    env = app_state.user_envs.setdefault(user_id, {})
    rules = app_state.user_rules.setdefault(user_id, {})
    interp = SplitLangInterpreter(
        db=db, owner_user_id=user_id, active_group_id=gid, env=env, rules=rules
    )
    app_state.active_groups[user_id] = interp.ctx.active_group_id
    return interp
