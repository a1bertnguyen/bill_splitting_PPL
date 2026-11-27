"""
Security HTTP Middleware for SplitLang FastAPI Backend.

Implements:
  - Control #18 (Add security headers): Strict CSP, X-Content-Type-Options, X-Frame-Options,
    Referrer-Policy, Permissions-Policy, Cache-Control: no-store on /api/*
  - Control #19 (Force HTTPS): Enforces HTTPS redirect & HSTS when FORCE_HTTPS=true
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from module.config import Settings

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        # Control #19: Force HTTPS redirect in production (respects reverse-proxy X-Forwarded-Proto)
        if self.settings.force_https:
            proto = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
            if proto != "https":
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=307)

        response = await call_next(request)

        # Control #18: Security Headers
        response.headers["Content-Security-Policy"] = CSP_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        if self.settings.force_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        return response
