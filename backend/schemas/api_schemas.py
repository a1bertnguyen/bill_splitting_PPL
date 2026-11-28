"""
Strict Pydantic v2 Request & Trimmed Response Schemas.

Implements:
  - Control #8  (Block field tampering): ConfigDict(extra="forbid") on ALL request models
  - Control #14 (Validate all input)   : Strict lengths, regexes, Literal allowlists, password policy
  - Control #17 (Trim API responses)   : Explicit public output models omitting hashes/internal IDs
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.security import (
    EMAIL_RE,
    USERNAME_RE,
    sanitize_control_chars,
    validate_password_strength,
)


class StrictModel(BaseModel):
    """Rejects any unknown/tampered fields (prevents mass-assignment attacks)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class RegisterRequest(StrictModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    # Control #12 (Bot protection): honeypot + signed challenge + answer
    website: str = Field(default="", max_length=64)
    challenge_token: str = Field(..., min_length=10, max_length=512)
    challenge_answer: str = Field(..., min_length=1, max_length=16)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        clean = v.strip()
        if not USERNAME_RE.match(clean):
            raise ValueError("Username must be 3-32 chars (letters, digits, _, ., -).")
        return clean

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        clean = v.strip().lower()
        if not EMAIL_RE.match(clean):
            raise ValueError("Invalid email address format.")
        return clean

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class LoginRequest(StrictModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)
    website: str = Field(default="", max_length=64)
    challenge_token: str = Field(..., min_length=10, max_length=512)
    challenge_answer: str = Field(..., min_length=1, max_length=16)


class ExecuteRequest(StrictModel):
    code: str = Field(..., min_length=1, max_length=16000)
    group_id: int | None = Field(default=None, ge=1)

    @field_validator("code")
    @classmethod
    def sanitize_code(cls, v: str) -> str:
        return sanitize_control_chars(v)


class DemoRequest(StrictModel):
    name: Literal["dinner", "trip"] = "dinner"


# ------------------------------------------------------------------
# Trimmed Public Response Schemas (Control #17)
# ------------------------------------------------------------------


class UserPublic(BaseModel):
    username: str
    email: str | None = None
    role: str


class AuthResponse(BaseModel):
    user: UserPublic
    csrf_token: str


class UploadResponse(BaseModel):
    filename: str
    code: str
    size_bytes: int


class ExecutionPayload(BaseModel):
    ok: bool
    stage_failed: str | None
    messages: list[str]
    ops: list[dict[str, Any]]
    tokens: list[dict[str, Any]]
    parse_tree: str
    ast_tree: str
    errors: list[str]
