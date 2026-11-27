"""
Core security primitives for SplitLang.

Implements:
  - Control #5  : Authenticated symmetric field encryption (Fernet AES + HMAC-SHA256)
  - Control #9  : Opaque session token hashing & constant-time CSRF verification
  - Control #10 : Argon2id adaptive password hashing
  - Control #11 : Sliding-window rate limiter with Retry-After lockout
  - Control #12 : Bot protection (honeypot + HMAC-signed single-use challenge + timing check)
  - Control #15 : Control-character sanitization for user text
  - Control #16 : Strict .split file upload validator (extension, size, UTF-8, null-byte guard)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

# Control #10: Argon2id password hasher (OWASP recommended parameters)
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,180}\.[^@\s]{2,24}$")
SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")
MAX_UPLOAD_BYTES = 64 * 1024  # 64 KB max .split script upload


# ============================================================================
# Control #10: Password Hashing (Argon2id) & Password Policy
# ============================================================================


def validate_password_strength(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters.")
    if not any(c.islower() for c in password):
        raise ValueError("Password must include at least one lowercase letter.")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must include at least one uppercase letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must include at least one digit.")


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# ============================================================================
# Control #5: Field-Level Encryption at Rest (Fernet AES-128-CBC + HMAC-SHA256)
# ============================================================================


class FieldEncryptor:
    """Encrypts sensitive text/JSON columns before DB storage and decrypts on read."""

    def __init__(self, fernet_key: str) -> None:
        self._fernet = Fernet(fernet_key.encode("ascii"))

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt protected record (invalid key or tampered ciphertext).") from exc


# ============================================================================
# Control #9: Opaque Session & CSRF Tokens
# ============================================================================


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def verify_csrf_token(expected: str, provided: str | None) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


# ============================================================================
# Control #11: Sliding-Window Rate Limiter (Login & API Abuse Protection)
# ============================================================================


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter returning (allowed, retry_after_sec)."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, record: bool = True) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        q = self._events[key]
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - q[0])))
            return False, retry_after
        if record:
            q.append(now)
        return True, 0

    def reset(self, key: str) -> None:
        self._events.pop(key, None)


# ============================================================================
# Control #12: Bot Protection (Honeypot + Signed Single-Use Challenge)
# ============================================================================


class BotProtector:
    """
    Self-hosted anti-bot guard for registration/login:
      1. Hidden honeypot field must remain empty.
      2. HMAC-signed arithmetic challenge token (single-use, 10-minute TTL).
      3. Optional minimum human-solve elapsed time (disabled in automated unit tests).
    """

    def __init__(self, secret_key: str, *, min_solve_seconds: float = 0.0, ttl_seconds: int = 600) -> None:
        self._secret = secret_key.encode("utf-8")
        self.min_solve_seconds = min_solve_seconds
        self.ttl_seconds = ttl_seconds
        self._used_nonces: dict[str, float] = {}

    def _sign(self, payload_b64: str) -> str:
        return hmac.new(self._secret, payload_b64.encode("ascii"), hashlib.sha256).hexdigest()

    def _prune_nonces(self, now: float) -> None:
        expired = [k for k, exp in self._used_nonces.items() if exp <= now]
        for k in expired:
            del self._used_nonces[k]

    def issue_challenge(self) -> dict[str, Any]:
        a = secrets.randbelow(8) + 2  # 2..9
        b = secrets.randbelow(8) + 2  # 2..9
        nonce = secrets.token_hex(12)
        issued_at = int(time.time())
        payload = {"n": nonce, "ans": a + b, "iat": issued_at}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        token = f"{payload_b64}.{self._sign(payload_b64)}"
        return {
            "challenge_token": token,
            "question": f"{a} + {b}",
            "expires_in": self.ttl_seconds,
        }

    def verify(self, *, honeypot: str, challenge_token: str, answer: str) -> tuple[bool, str]:
        if honeypot.strip() != "":
            return False, "Bot protection triggered."

        if not challenge_token or "." not in challenge_token:
            return False, "Missing or malformed verification challenge."

        payload_b64, provided_sig = challenge_token.rsplit(".", 1)
        expected_sig = self._sign(payload_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return False, "Invalid verification challenge signature."

        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        except Exception:
            return False, "Corrupted verification challenge."

        now = time.time()
        self._prune_nonces(now)
        nonce = str(payload.get("n", ""))
        iat = float(payload.get("iat", 0))
        expected_ans = int(payload.get("ans", -1))

        if now - iat > self.ttl_seconds:
            return False, "Verification challenge expired. Please refresh the challenge."
        if self.min_solve_seconds > 0 and (now - iat) < self.min_solve_seconds:
            return False, "Submission too fast. Please wait a moment and try again."
        if nonce in self._used_nonces:
            return False, "Verification challenge already used. Please request a new one."

        try:
            user_ans = int(str(answer).strip())
        except ValueError:
            return False, "Verification answer must be an integer."

        if user_ans != expected_ans:
            return False, "Incorrect anti-bot verification answer."

        self._used_nonces[nonce] = now + self.ttl_seconds
        return True, ""


# ============================================================================
# Control #15 & #16: Text Sanitization & Strict .split File Upload Validation
# ============================================================================


def sanitize_control_chars(text: str) -> str:
    """Strip non-printable ASCII control characters while preserving tabs and newlines."""
    return "".join(ch for ch in text if ch in ("\n", "\r", "\t") or ord(ch) >= 32)


def validate_split_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    """
    Strictly validate an uploaded SplitLang script:
      - Safe basename, .split extension only (no path traversal, no executable/HTML types)
      - Size <= 64 KB and non-empty
      - No null bytes (rejects binary/polyglot files)
      - Valid UTF-8 text
    Returns (sanitized_filename, decoded_utf8_text).
    """
    if not filename:
        raise ValueError("Missing filename.")
    clean_name = Path(filename).name
    if clean_name != filename and ("/" in filename or "\\" in filename or ".." in filename):
        raise ValueError("Invalid filename (path traversal blocked).")
    if not SAFE_FILENAME_RE.match(clean_name) or not clean_name.lower().endswith(".split"):
        raise ValueError("Only plain '.split' script files with safe filenames are allowed.")
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file exceeds maximum allowed size ({MAX_UPLOAD_BYTES // 1024} KB).")
    if b"\x00" in content:
        raise ValueError("Binary content detected and rejected.")
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Uploaded file must be valid UTF-8 plain text.") from exc
    return clean_name, sanitize_control_chars(decoded)
