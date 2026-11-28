"""
Row-Level-Secured Database Layer for SplitLang (MySQL 8.x/9.x primary + SQLite test fallback).

Security controls enforced here:
  - Control #3  : Connects using least-privilege MySQL credentials from .env
  - Control #4  : Row-Level Security (every query & record scoped by owner_user_id)
  - Control #5  : Encrypts sensitive text/JSON columns at rest via FieldEncryptor (Fernet)
  - Control #7  : Locks record access — cross-user group/record access raises PermissionError
  - Control #13 : 100% parameterized SQL queries (zero string interpolation of user input)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

import pymysql
from pymysql.cursors import DictCursor

from backend.core.config import Settings, load_settings
from backend.core.security import FieldEncryptor


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "splitlang.db"


class Database:
    """
    Unified MySQL + SQLite persistence layer with mandatory row-level ownership isolation
    and at-rest field encryption.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        settings: Settings | None = None,
        backend: str | None = None,
    ) -> None:
        self.settings = settings or load_settings(allow_ephemeral_keys=True)
        self.encryptor = FieldEncryptor(self.settings.data_encryption_key)

        # If caller explicitly passes a sqlite path (e.g. ":memory:" in unit tests), use sqlite.
        if db_path is not None:
            self.backend = "sqlite"
        else:
            self.backend = (backend or self.settings.db_backend).lower()

        if self.backend == "mysql":
            self._connect_mysql()
        else:
            self._connect_sqlite(db_path)

        self._init_schema()

    # ------------------------------------------------------------------
    # Connection & Parameterized Query Adapter (Control #13)
    # ------------------------------------------------------------------

    def _connect_mysql(self) -> None:
        self.conn = pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    def _connect_sqlite(self, db_path: str | Path | None) -> None:
        if db_path is None:
            DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            resolved = str(DEFAULT_SQLITE_PATH)
        elif str(db_path) == ":memory:":
            resolved = ":memory:"
        else:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            resolved = str(p)

        self.conn = sqlite3.connect(resolved, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def _adapt_sql(self, sql: str) -> str:
        """Convert `%s` placeholders to `?` when running on SQLite."""
        if self.backend == "sqlite":
            return sql.replace("%s", "?")
        return sql

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        adapted = self._adapt_sql(sql)
        if self.backend == "mysql":
            self.conn.ping(reconnect=True)
            cur = self.conn.cursor()
            cur.execute(adapted, params)
            return cur
        return self.conn.execute(adapted, params)

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        cur = self._execute(sql, params)
        row = cur.fetchone()
        if self.backend == "mysql":
            cur.close()
        return dict(row) if row is not None else None

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        if self.backend == "mysql":
            cur.close()
        return [dict(r) for r in rows]

    def _insert(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        cur = self._execute(sql, params)
        last_id = int(cur.lastrowid)
        if self.backend == "mysql":
            cur.close()
        return last_id

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Schema Initialization
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        if self.backend == "mysql":
            stmts = [
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(64)  NOT NULL UNIQUE,
                    email_enc     TEXT         NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role          VARCHAR(16)  NOT NULL DEFAULT 'user',
                    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id       BIGINT UNSIGNED NOT NULL,
                    token_hash    CHAR(64)        NOT NULL UNIQUE,
                    csrf_token    CHAR(64)        NOT NULL,
                    expires_at    DATETIME        NOT NULL,
                    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_sessions_user (user_id),
                    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS `groups` (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id BIGINT UNSIGNED NOT NULL,
                    name          VARCHAR(120)    NOT NULL,
                    currency      VARCHAR(8)      NOT NULL DEFAULT 'VND',
                    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_group_owner_name (owner_user_id, name),
                    INDEX idx_groups_owner (owner_user_id),
                    CONSTRAINT fk_groups_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS members (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id BIGINT UNSIGNED NOT NULL,
                    group_id      BIGINT UNSIGNED NOT NULL,
                    name          VARCHAR(64)     NOT NULL,
                    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_member_group_name (group_id, name),
                    INDEX idx_members_owner_group (owner_user_id, group_id),
                    CONSTRAINT fk_members_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id   BIGINT UNSIGNED NOT NULL,
                    group_id        BIGINT UNSIGNED NOT NULL,
                    kind            VARCHAR(16)     NOT NULL DEFAULT 'expense',
                    payer           VARCHAR(64)     NOT NULL,
                    description_enc TEXT            NOT NULL,
                    subtotal        VARCHAR(40)     NOT NULL,
                    tax_amount      VARCHAR(40)     NOT NULL DEFAULT '0',
                    tip_amount      VARCHAR(40)     NOT NULL DEFAULT '0',
                    discount        VARCHAR(40)     NOT NULL DEFAULT '0',
                    total           VARCHAR(40)     NOT NULL,
                    split_mode      VARCHAR(24)     NOT NULL,
                    items_enc       MEDIUMTEXT      NULL,
                    expense_date    VARCHAR(16)     NOT NULL,
                    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_expenses_owner_group (owner_user_id, group_id),
                    CONSTRAINT fk_expenses_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS expense_shares (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id BIGINT UNSIGNED NOT NULL,
                    expense_id    BIGINT UNSIGNED NOT NULL,
                    member_name   VARCHAR(64)     NOT NULL,
                    share_amount  VARCHAR(40)     NOT NULL,
                    INDEX idx_shares_expense (expense_id),
                    CONSTRAINT fk_shares_expense FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS settlements (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id BIGINT UNSIGNED NOT NULL,
                    group_id      BIGINT UNSIGNED NOT NULL,
                    from_member   VARCHAR(64)     NOT NULL,
                    to_member     VARCHAR(64)     NOT NULL,
                    amount        VARCHAR(40)     NOT NULL,
                    note_enc      TEXT            NOT NULL,
                    settle_date   VARCHAR(16)     NOT NULL,
                    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_settlements_owner_group (owner_user_id, group_id),
                    CONSTRAINT fk_settlements_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
                """
                CREATE TABLE IF NOT EXISTS action_log (
                    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    owner_user_id BIGINT UNSIGNED NOT NULL,
                    group_id      BIGINT UNSIGNED NOT NULL,
                    action_type   VARCHAR(24)     NOT NULL,
                    record_id     BIGINT UNSIGNED NOT NULL,
                    summary_enc   TEXT            NOT NULL,
                    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_log_owner_group (owner_user_id, group_id),
                    CONSTRAINT fk_log_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """,
            ]
            for stmt in stmts:
                cur = self._execute(stmt)
                cur.close()
            self.conn.commit()
        else:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    email_enc     TEXT,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL DEFAULT 'user',
                    created_at    TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    token_hash    TEXT NOT NULL UNIQUE,
                    csrf_token    TEXT NOT NULL,
                    expires_at    TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS `groups` (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    name          TEXT NOT NULL COLLATE NOCASE,
                    currency      TEXT NOT NULL DEFAULT 'VND',
                    created_at    TEXT NOT NULL,
                    UNIQUE(owner_user_id, name),
                    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS members (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    group_id      INTEGER NOT NULL,
                    name          TEXT NOT NULL COLLATE NOCASE,
                    created_at    TEXT NOT NULL,
                    UNIQUE(group_id, name),
                    FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS expenses (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id   INTEGER NOT NULL,
                    group_id        INTEGER NOT NULL,
                    kind            TEXT NOT NULL DEFAULT 'expense',
                    payer           TEXT NOT NULL,
                    description_enc TEXT NOT NULL,
                    subtotal        TEXT NOT NULL,
                    tax_amount      TEXT NOT NULL DEFAULT '0',
                    tip_amount      TEXT NOT NULL DEFAULT '0',
                    discount        TEXT NOT NULL DEFAULT '0',
                    total           TEXT NOT NULL,
                    split_mode      TEXT NOT NULL,
                    items_enc       TEXT,
                    expense_date    TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS expense_shares (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    expense_id    INTEGER NOT NULL,
                    member_name   TEXT NOT NULL,
                    share_amount  TEXT NOT NULL,
                    FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS settlements (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    group_id      INTEGER NOT NULL,
                    from_member   TEXT NOT NULL,
                    to_member     TEXT NOT NULL,
                    amount        TEXT NOT NULL,
                    note_enc      TEXT NOT NULL,
                    settle_date   TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS action_log (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    group_id      INTEGER NOT NULL,
                    action_type   TEXT NOT NULL,
                    record_id     INTEGER NOT NULL,
                    summary_enc   TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
                );
                """
            )
            self.conn.commit()

    # ------------------------------------------------------------------
    # Users & Server-Side Sessions (Controls #5, #6, #9, #10)
    # ------------------------------------------------------------------

    def ensure_local_cli_user(self) -> int:
        row = self._fetchone("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", ("cli_local",))
        if row:
            return int(row["id"])
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        uid = self._insert(
            "INSERT INTO users (username, email_enc, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            ("cli_local", None, "!locked-local-cli-account!", "user", now),
        )
        self.conn.commit()
        return uid

    def create_user(self, *, username: str, email: str | None, password_hash: str) -> dict[str, Any]:
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        email_enc = self.encryptor.encrypt(email) if email else None
        uid = self._insert(
            "INSERT INTO users (username, email_enc, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
            (username, email_enc, password_hash, "user", now),
        )
        self.conn.commit()
        user = self.get_user_by_id(uid)
        assert user is not None
        return user

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT id, username, email_enc, password_hash, role, created_at FROM users WHERE LOWER(username) = LOWER(%s)",
            (username,),
        )
        if not row:
            return None
        row["email"] = self.encryptor.decrypt(row["email_enc"]) if row["email_enc"] else None
        return row

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT id, username, email_enc, role, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        if not row:
            return None
        row["email"] = self.encryptor.decrypt(row["email_enc"]) if row["email_enc"] else None
        row.pop("email_enc", None)
        return row

    def create_session(self, *, user_id: int, token_hash: str, csrf_token: str, ttl_hours: int) -> dict[str, Any]:
        now_dt = _utc_now()
        exp_dt = now_dt + timedelta(hours=ttl_hours)
        now_s = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        exp_s = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        sid = self._insert(
            "INSERT INTO sessions (user_id, token_hash, csrf_token, expires_at, created_at) VALUES (%s, %s, %s, %s, %s)",
            (user_id, token_hash, csrf_token, exp_s, now_s),
        )
        self.conn.commit()
        return {"id": sid, "user_id": user_id, "csrf_token": csrf_token, "expires_at": exp_s}

    def get_session_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT s.id, s.user_id, s.csrf_token, s.expires_at, u.username, u.role
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s
            """,
            (token_hash,),
        )
        if not row:
            return None
        exp = row["expires_at"]
        exp_dt = exp if isinstance(exp, datetime) else datetime.strptime(str(exp), "%Y-%m-%d %H:%M:%S")
        if exp_dt < _utc_now():
            self.delete_session(token_hash)
            return None
        return row

    def delete_session(self, token_hash: str) -> None:
        cur = self._execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
        if self.backend == "mysql":
            cur.close()
        self.conn.commit()

    # ------------------------------------------------------------------
    # Ownership Guard (Controls #4 & #7: Row-Level Security & IDOR Lock)
    # ------------------------------------------------------------------

    def _assert_group_owner(self, group_id: int, owner_user_id: int) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT id, owner_user_id, name, currency, created_at FROM `groups` WHERE id = %s AND owner_user_id = %s",
            (group_id, owner_user_id),
        )
        if not row:
            raise PermissionError("Access denied: group not found or locked to another account.")
        return row

    # ------------------------------------------------------------------
    # Groups & Currency (Scoped by owner_user_id)
    # ------------------------------------------------------------------

    def ensure_group(self, name: str, currency: str = "VND", *, owner_user_id: int) -> dict[str, Any]:
        clean = name.strip()
        row = self._fetchone(
            "SELECT id, owner_user_id, name, currency, created_at FROM `groups` WHERE owner_user_id = %s AND LOWER(name) = LOWER(%s)",
            (owner_user_id, clean),
        )
        if row:
            return row
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        gid = self._insert(
            "INSERT INTO `groups` (owner_user_id, name, currency, created_at) VALUES (%s, %s, %s, %s)",
            (owner_user_id, clean, currency.upper(), now),
        )
        self.conn.commit()
        return self.get_group_by_id(gid, owner_user_id=owner_user_id)

    def get_group_by_id(self, group_id: int, *, owner_user_id: int) -> dict[str, Any]:
        return self._assert_group_owner(group_id, owner_user_id)

    def get_group_by_name(self, name: str, *, owner_user_id: int) -> dict[str, Any] | None:
        return self._fetchone(
            "SELECT id, owner_user_id, name, currency, created_at FROM `groups` WHERE owner_user_id = %s AND LOWER(name) = LOWER(%s)",
            (owner_user_id, name.strip()),
        )

    def list_groups(self, *, owner_user_id: int) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT g.id, g.name, g.currency, g.created_at,
                   (SELECT COUNT(*) FROM members m WHERE m.group_id = g.id AND m.owner_user_id = g.owner_user_id) AS member_count,
                   (SELECT COUNT(*) FROM expenses e WHERE e.group_id = g.id AND e.owner_user_id = g.owner_user_id) AS expense_count
            FROM `groups` g
            WHERE g.owner_user_id = %s
            ORDER BY g.id ASC
            """,
            (owner_user_id,),
        )

    def set_currency(self, group_id: int, currency: str, *, owner_user_id: int) -> dict[str, Any]:
        self._assert_group_owner(group_id, owner_user_id)
        cur = self._execute(
            "UPDATE `groups` SET currency = %s WHERE id = %s AND owner_user_id = %s",
            (currency.upper(), group_id, owner_user_id),
        )
        if self.backend == "mysql":
            cur.close()
        self.conn.commit()
        return self.get_group_by_id(group_id, owner_user_id=owner_user_id)

    # ------------------------------------------------------------------
    # Members (Scoped by owner_user_id)
    # ------------------------------------------------------------------

    def add_members(self, group_id: int, names: list[str], *, owner_user_id: int) -> tuple[list[str], list[str]]:
        self._assert_group_owner(group_id, owner_user_id)
        added: list[str] = []
        existed: list[str] = []
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        for raw in names:
            clean = raw.strip()
            existing = self._fetchone(
                "SELECT name FROM members WHERE group_id = %s AND owner_user_id = %s AND LOWER(name) = LOWER(%s)",
                (group_id, owner_user_id, clean),
            )
            if existing:
                existed.append(existing["name"])
            else:
                self._insert(
                    "INSERT INTO members (owner_user_id, group_id, name, created_at) VALUES (%s, %s, %s, %s)",
                    (owner_user_id, group_id, clean, now),
                )
                added.append(clean)
        self.conn.commit()
        return added, existed

    def remove_members(self, group_id: int, names: list[str], *, owner_user_id: int) -> tuple[list[str], list[str]]:
        self._assert_group_owner(group_id, owner_user_id)
        removed: list[str] = []
        not_found: list[str] = []
        for raw in names:
            clean = raw.strip()
            row = self._fetchone(
                "SELECT id, name FROM members WHERE group_id = %s AND owner_user_id = %s AND LOWER(name) = LOWER(%s)",
                (group_id, owner_user_id, clean),
            )
            if row:
                cur = self._execute(
                    "DELETE FROM members WHERE id = %s AND owner_user_id = %s",
                    (row["id"], owner_user_id),
                )
                if self.backend == "mysql":
                    cur.close()
                removed.append(row["name"])
            else:
                not_found.append(clean)
        self.conn.commit()
        return removed, not_found

    def list_members(self, group_id: int, *, owner_user_id: int) -> list[str]:
        self._assert_group_owner(group_id, owner_user_id)
        rows = self._fetchall(
            "SELECT name FROM members WHERE group_id = %s AND owner_user_id = %s ORDER BY id ASC",
            (group_id, owner_user_id),
        )
        return [r["name"] for r in rows]

    def resolve_member_name(self, group_id: int, name: str, *, owner_user_id: int) -> str | None:
        self._assert_group_owner(group_id, owner_user_id)
        row = self._fetchone(
            "SELECT name FROM members WHERE group_id = %s AND owner_user_id = %s AND LOWER(name) = LOWER(%s)",
            (group_id, owner_user_id, name.strip()),
        )
        return row["name"] if row else None

    # ------------------------------------------------------------------
    # Expenses & Bills (Encrypted at rest, Scoped by owner_user_id)
    # ------------------------------------------------------------------

    def add_expense(
        self,
        group_id: int,
        *,
        owner_user_id: int,
        kind: str,
        payer: str,
        description: str,
        subtotal: Decimal,
        tax_amount: Decimal,
        tip_amount: Decimal,
        discount: Decimal,
        total: Decimal,
        split_mode: str,
        shares: dict[str, Decimal],
        expense_date: str,
        items: list[dict[str, Any]] | None = None,
    ) -> int:
        self._assert_group_owner(group_id, owner_user_id)
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        desc_enc = self.encryptor.encrypt(description)
        items_enc = self.encryptor.encrypt(json.dumps(items)) if items is not None else None

        expense_id = self._insert(
            """
            INSERT INTO expenses (
                owner_user_id, group_id, kind, payer, description_enc, subtotal,
                tax_amount, tip_amount, discount, total,
                split_mode, items_enc, expense_date, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_user_id,
                group_id,
                kind,
                payer,
                desc_enc,
                str(subtotal),
                str(tax_amount),
                str(tip_amount),
                str(discount),
                str(total),
                split_mode,
                items_enc,
                expense_date,
                now,
            ),
        )
        for member_name, share_amt in shares.items():
            self._insert(
                "INSERT INTO expense_shares (owner_user_id, expense_id, member_name, share_amount) VALUES (%s, %s, %s, %s)",
                (owner_user_id, expense_id, member_name, str(share_amt)),
            )
        summary_enc = self.encryptor.encrypt(
            f"{kind.capitalize()} #{expense_id}: {payer} paid {total} for '{description}'"
        )
        self._insert(
            "INSERT INTO action_log (owner_user_id, group_id, action_type, record_id, summary_enc, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (owner_user_id, group_id, "expense", expense_id, summary_enc, now),
        )
        self.conn.commit()
        return expense_id

    def list_expenses(self, group_id: int, *, owner_user_id: int) -> list[dict[str, Any]]:
        self._assert_group_owner(group_id, owner_user_id)
        rows = self._fetchall(
            "SELECT * FROM expenses WHERE group_id = %s AND owner_user_id = %s ORDER BY id ASC",
            (group_id, owner_user_id),
        )
        result: list[dict[str, Any]] = []
        for item in rows:
            share_rows = self._fetchall(
                "SELECT member_name, share_amount FROM expense_shares WHERE expense_id = %s AND owner_user_id = %s ORDER BY id ASC",
                (item["id"], owner_user_id),
            )
            item["description"] = self.encryptor.decrypt(item.pop("description_enc")) or ""
            items_enc = item.pop("items_enc")
            item["items"] = json.loads(self.encryptor.decrypt(items_enc)) if items_enc else None
            item["shares"] = {sr["member_name"]: Decimal(sr["share_amount"]) for sr in share_rows}
            item["subtotal"] = Decimal(item["subtotal"])
            item["tax_amount"] = Decimal(item["tax_amount"])
            item["tip_amount"] = Decimal(item["tip_amount"])
            item["discount"] = Decimal(item["discount"])
            item["total"] = Decimal(item["total"])
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # Settlements (Encrypted note, Scoped by owner_user_id)
    # ------------------------------------------------------------------

    def add_settlement(
        self,
        group_id: int,
        *,
        owner_user_id: int,
        from_member: str,
        to_member: str,
        amount: Decimal,
        note: str,
        settle_date: str,
    ) -> int:
        self._assert_group_owner(group_id, owner_user_id)
        now = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
        note_enc = self.encryptor.encrypt(note)
        settle_id = self._insert(
            """
            INSERT INTO settlements (
                owner_user_id, group_id, from_member, to_member, amount, note_enc, settle_date, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (owner_user_id, group_id, from_member, to_member, str(amount), note_enc, settle_date, now),
        )
        summary_enc = self.encryptor.encrypt(
            f"Settlement #{settle_id}: {from_member} -> {to_member} ({amount})"
        )
        self._insert(
            "INSERT INTO action_log (owner_user_id, group_id, action_type, record_id, summary_enc, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (owner_user_id, group_id, "settlement", settle_id, summary_enc, now),
        )
        self.conn.commit()
        return settle_id

    def list_settlements(self, group_id: int, *, owner_user_id: int) -> list[dict[str, Any]]:
        self._assert_group_owner(group_id, owner_user_id)
        rows = self._fetchall(
            "SELECT * FROM settlements WHERE group_id = %s AND owner_user_id = %s ORDER BY id ASC",
            (group_id, owner_user_id),
        )
        for item in rows:
            item["note"] = self.encryptor.decrypt(item.pop("note_enc")) or ""
            item["amount"] = Decimal(item["amount"])
        return rows

    # ------------------------------------------------------------------
    # Undo & Reset (Scoped by owner_user_id)
    # ------------------------------------------------------------------

    def undo_last_action(self, group_id: int, *, owner_user_id: int) -> str | None:
        self._assert_group_owner(group_id, owner_user_id)
        row = self._fetchone(
            "SELECT * FROM action_log WHERE group_id = %s AND owner_user_id = %s ORDER BY id DESC LIMIT 1",
            (group_id, owner_user_id),
        )
        if not row:
            return None

        if row["action_type"] == "expense":
            cur = self._execute(
                "DELETE FROM expenses WHERE id = %s AND owner_user_id = %s",
                (row["record_id"], owner_user_id),
            )
            if self.backend == "mysql":
                cur.close()
        elif row["action_type"] == "settlement":
            cur = self._execute(
                "DELETE FROM settlements WHERE id = %s AND owner_user_id = %s",
                (row["record_id"], owner_user_id),
            )
            if self.backend == "mysql":
                cur.close()

        cur = self._execute(
            "DELETE FROM action_log WHERE id = %s AND owner_user_id = %s",
            (row["id"], owner_user_id),
        )
        if self.backend == "mysql":
            cur.close()
        self.conn.commit()
        return self.encryptor.decrypt(row["summary_enc"]) or ""

    def reset_group(self, group_id: int, *, owner_user_id: int) -> None:
        self._assert_group_owner(group_id, owner_user_id)
        for tbl in ("expenses", "settlements", "action_log", "members"):
            cur = self._execute(
                f"DELETE FROM {tbl} WHERE group_id = %s AND owner_user_id = %s",
                (group_id, owner_user_id),
            )
            if self.backend == "mysql":
                cur.close()
        self.conn.commit()
