"""
Server-side configuration loader for SplitLang.

Control #1 (Hide API keys): All database credentials, cryptographic keys, and
security flags are loaded strictly from server-side environment variables (.env)
and NEVER bundled into the React frontend.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_PLACEHOLDERS = {
    "",
    "REPLACE_WITH_STRONG_MYSQL_APP_PASSWORD",
    "REPLACE_WITH_RANDOM_64_HEX_SECRET",
    "REPLACE_WITH_FERNET_KEY",
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_backend: str
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    secret_key: str
    data_encryption_key: str
    force_https: bool
    cookie_secure: bool
    cookie_samesite: str
    session_ttl_hours: int
    cors_origins: tuple[str, ...]
    login_rate_limit_max: int
    login_rate_limit_window_sec: int


def load_settings(*, allow_ephemeral_keys: bool = True) -> Settings:
    secret_key = os.getenv("SECRET_KEY", "").strip()
    enc_key = os.getenv("DATA_ENCRYPTION_KEY", "").strip()

    if secret_key in _PLACEHOLDERS:
        if not allow_ephemeral_keys:
            raise RuntimeError("SECRET_KEY is missing or placeholder. Run scripts/generate_secrets.py.")
        secret_key = secrets.token_hex(32)

    if enc_key in _PLACEHOLDERS:
        if not allow_ephemeral_keys:
            raise RuntimeError(
                "DATA_ENCRYPTION_KEY is missing or placeholder. Run scripts/generate_secrets.py."
            )
        enc_key = Fernet.generate_key().decode("ascii")

    cors_raw = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173",
    )
    cors_origins = tuple(o.strip() for o in cors_raw.split(",") if o.strip() and o.strip() != "*")

    samesite = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"

    force_https = _env_bool("FORCE_HTTPS", False)
    cookie_secure = _env_bool("COOKIE_SECURE", force_https)

    return Settings(
        db_backend=os.getenv("DB_BACKEND", "mysql").strip().lower(),
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_database=os.getenv("MYSQL_DATABASE", "splitlang_db").strip(),
        mysql_user=os.getenv("MYSQL_USER", "splitlang_app").strip(),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        secret_key=secret_key,
        data_encryption_key=enc_key,
        force_https=force_https,
        cookie_secure=cookie_secure,
        cookie_samesite=samesite,
        session_ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "12")),
        cors_origins=cors_origins,
        login_rate_limit_max=int(os.getenv("LOGIN_RATE_LIMIT_MAX", "5")),
        login_rate_limit_window_sec=int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SEC", "300")),
    )
