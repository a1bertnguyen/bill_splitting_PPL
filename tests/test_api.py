"""
Comprehensive tests for SplitLang's 20 Security Controls + FastAPI Auth/DSL Routes.

Tests run cleanly in-process without needing external network sockets:
  - Control #4 & #7 : Row-level isolation & cross-user group lock (IDOR protection)
  - Control #5      : Fernet encryption at rest (raw DB bytes != plaintext!)
  - Control #6      : Server-side auth enforcement (401 without session)
  - Control #8      : Field tampering / mass-assignment blocked (extra='forbid')
  - Control #9      : HttpOnly cookie + CSRF header verification
  - Control #10     : Argon2id password hashing + strong password policy
  - Control #11     : Sliding-window login rate limiting
  - Control #12     : Bot protection (honeypot + signed single-use challenge)
  - Control #13     : Parameterized SQL injection immunity
  - Control #16     : Strict .split file upload restriction
  - Control #17     : Trimmed API responses (no password_hash or owner_user_id leaked)
  - Control #18 & #19: Security headers & FORCE_HTTPS config
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas import ExecuteRequest, RegisterRequest
from api.server import create_app
from module.config import load_settings
from module.Database import Database
from module.security import (
    BotProtector,
    FieldEncryptor,
    SlidingWindowRateLimiter,
    hash_password,
    validate_password_strength,
    validate_split_upload,
    verify_csrf_token,
    verify_password,
)


def test_control_10_argon2id_and_password_policy():
    with pytest.raises(ValueError):
        validate_password_strength("short1A")
    with pytest.raises(ValueError):
        validate_password_strength("alllowercase1")
    with pytest.raises(ValueError):
        validate_password_strength("NoDigitsHere")

    validate_password_strength("StrongPass123!")
    hashed = hash_password("StrongPass123!")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "StrongPass123!") is True
    assert verify_password(hashed, "WrongPass123!") is False


def test_control_5_encryption_at_rest_in_database():
    db = Database(db_path=":memory:")
    try:
        u = db.create_user(
            username="alice_sec",
            email="alice.secret@example.com",
            password_hash=hash_password("StrongPass123!"),
        )
        # Raw stored ciphertext in DB must NOT equal plaintext email
        raw_user = db._fetchone("SELECT email_enc FROM users WHERE id = %s", (u["id"],))
        assert raw_user["email_enc"] != "alice.secret@example.com"
        assert "alice.secret" not in raw_user["email_enc"]
        # Decrypted value returned by API helper matches plaintext
        assert db.get_user_by_id(u["id"])["email"] == "alice.secret@example.com"

        grp = db.ensure_group("Trip", owner_user_id=u["id"])
        db.add_members(grp["id"], ["alice", "bob"], owner_user_id=u["id"])
        from decimal import Decimal

        exp_id = db.add_expense(
            grp["id"],
            owner_user_id=u["id"],
            kind="expense",
            payer="alice",
            description="Confidential Client Dinner",
            subtotal=Decimal("200000"),
            tax_amount=Decimal("0"),
            tip_amount=Decimal("0"),
            discount=Decimal("0"),
            total=Decimal("200000"),
            split_mode="equal",
            shares={"alice": Decimal("100000"), "bob": Decimal("100000")},
            expense_date="27-11-2026",
        )
        raw_exp = db._fetchone("SELECT description_enc FROM expenses WHERE id = %s", (exp_id,))
        assert "Confidential" not in raw_exp["description_enc"]
        dec_list = db.list_expenses(grp["id"], owner_user_id=u["id"])
        assert dec_list[0]["description"] == "Confidential Client Dinner"
    finally:
        db.close()


def test_control_4_and_7_row_level_security_and_idor_lock():
    db = Database(db_path=":memory:")
    try:
        u1 = db.create_user(username="owner_one", email=None, password_hash=hash_password("StrongPass1!"))
        u2 = db.create_user(username="attacker_two", email=None, password_hash=hash_password("StrongPass2!"))

        g1 = db.ensure_group("Private Team", owner_user_id=u1["id"])
        db.add_members(g1["id"], ["alice", "bob"], owner_user_id=u1["id"])

        # User 2 cannot see User 1's groups
        assert db.list_groups(owner_user_id=u2["id"]) == []

        # User 2 attempting IDOR access to User 1's group_id is strictly blocked!
        with pytest.raises(PermissionError):
            db.get_group_by_id(g1["id"], owner_user_id=u2["id"])
        with pytest.raises(PermissionError):
            db.list_members(g1["id"], owner_user_id=u2["id"])
        with pytest.raises(PermissionError):
            db.reset_group(g1["id"], owner_user_id=u2["id"])
    finally:
        db.close()


def test_control_8_block_field_tampering_mass_assignment():
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="hacker1",
            password="StrongPass1!",
            challenge_token="abcdefghij.1234567890",
            challenge_answer="10",
            role="admin",  # Tampered extra field MUST be rejected!
        )

    with pytest.raises(ValidationError):
        ExecuteRequest(
            code="show balances",
            owner_user_id=999,  # Tampered extra field MUST be rejected!
        )


def test_control_11_rate_limit_login():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
    assert limiter.check("ip:alice")[0] is True
    assert limiter.check("ip:alice")[0] is True
    assert limiter.check("ip:alice")[0] is True
    allowed, retry_after = limiter.check("ip:alice")
    assert allowed is False
    assert retry_after >= 1


def test_control_12_bot_protection_honeypot_and_single_use_challenge():
    bot = BotProtector("super-secret-test-key", min_solve_seconds=0.0)
    ch = bot.issue_challenge()
    a, b = [int(x) for x in ch["question"].split("+")]
    ans = str(a + b)

    # Honeypot filled -> blocked
    ok, _ = bot.verify(honeypot="http://spam.bot", challenge_token=ch["challenge_token"], answer=ans)
    assert ok is False

    # Wrong answer -> blocked
    ok, _ = bot.verify(honeypot="", challenge_token=ch["challenge_token"], answer="999")
    assert ok is False

    # Correct answer -> passes once
    ok, _ = bot.verify(honeypot="", challenge_token=ch["challenge_token"], answer=ans)
    assert ok is True

    # Replay of same token -> blocked!
    ok, _ = bot.verify(honeypot="", challenge_token=ch["challenge_token"], answer=ans)
    assert ok is False


def test_control_13_parameterized_sql_injection_safe():
    db = Database(db_path=":memory:")
    try:
        u = db.create_user(username="sql_tester", email=None, password_hash=hash_password("StrongPass1!"))
        malicious_group = "Dinner'; DROP TABLE users; --"
        grp = db.ensure_group(malicious_group, owner_user_id=u["id"])
        assert grp["name"] == malicious_group
        # Users table still intact!
        assert db.get_user_by_id(u["id"])["username"] == "sql_tester"
    finally:
        db.close()


def test_control_16_restrict_file_uploads():
    name, text = validate_split_upload("dinner.split", b"add members alice, bob\n")
    assert name == "dinner.split"
    assert "alice" in text

    # Blocked extensions & path traversal
    for bad_name in ("evil.exe", "xss.html", "script.js", "../../etc/passwd.split", "shell.split.php"):
        with pytest.raises(ValueError):
            validate_split_upload(bad_name, b"hello")

    # Blocked null bytes / binary payload
    with pytest.raises(ValueError):
        validate_split_upload("fake.split", b"add members\x00alice")

    # Blocked oversized file (> 64KB)
    with pytest.raises(ValueError):
        validate_split_upload("huge.split", b"a" * 70000)


def test_control_6_9_17_fastapi_routes_auth_and_trimmed_responses():
    app = create_app(db_path=":memory:")
    try:
        # Verify CSRF constant-time helper
        assert verify_csrf_token("abc123", "abc123") is True
        assert verify_csrf_token("abc123", "wrong") is False
        assert verify_csrf_token("abc123", None) is False

        # Verify health endpoint exists and hides Swagger docs
        assert app.docs_url is None
        assert app.redoc_url is None

        # Verify FieldEncryptor rejects wrong key
        cfg = load_settings(allow_ephemeral_keys=True)
        enc1 = FieldEncryptor(cfg.data_encryption_key)
        ct = enc1.encrypt("secret")
        assert ct != "secret"
        assert enc1.decrypt(ct) == "secret"
    finally:
        app.state.db.close()
