"""
SQLite persistence layer for SplitLang.

Zero-setup local storage (no external database daemon required).
Supports multiple groups, members, itemized/standard expenses, per-person shares,
repayment settlements, and undo history.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "splitlang.db"


class Database:
    """Local SQLite database manager for SplitLang."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(DEFAULT_DB_PATH)
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(p)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._init_schema()
        self.ensure_group("Default", currency="VND")

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
                currency    TEXT NOT NULL DEFAULT 'VND',
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS members (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                name        TEXT NOT NULL COLLATE NOCASE,
                created_at  TEXT NOT NULL,
                UNIQUE(group_id, name),
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                kind        TEXT NOT NULL DEFAULT 'expense', -- 'expense' or 'bill'
                payer       TEXT NOT NULL,
                description TEXT NOT NULL,
                subtotal    TEXT NOT NULL,
                tax_amount  TEXT NOT NULL DEFAULT '0',
                tip_amount  TEXT NOT NULL DEFAULT '0',
                discount    TEXT NOT NULL DEFAULT '0',
                total       TEXT NOT NULL,
                split_mode  TEXT NOT NULL,
                items_json  TEXT,
                expense_date TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS expense_shares (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id  INTEGER NOT NULL,
                member_name TEXT NOT NULL,
                share_amount TEXT NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settlements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                from_member TEXT NOT NULL,
                to_member   TEXT NOT NULL,
                amount      TEXT NOT NULL,
                note        TEXT NOT NULL DEFAULT '',
                settle_date TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS action_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                action_type TEXT NOT NULL, -- 'expense' or 'settlement'
                record_id   INTEGER NOT NULL,
                summary     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------
    # Groups & Currency
    # ------------------------------------------------------------------

    def ensure_group(self, name: str, currency: str = "VND") -> dict[str, Any]:
        clean = name.strip()
        row = self.conn.execute(
            "SELECT * FROM groups WHERE name = ? COLLATE NOCASE", (clean,)
        ).fetchone()
        if row:
            return dict(row)
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "INSERT INTO groups (name, currency, created_at) VALUES (?, ?, ?)",
            (clean, currency.upper(), now),
        )
        self.conn.commit()
        return self.get_group_by_id(cur.lastrowid)

    def get_group_by_id(self, group_id: int) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Group ID {group_id} not found.")
        return dict(row)

    def get_group_by_name(self, name: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM groups WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ).fetchone()
        return dict(row) if row else None

    def list_groups(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT g.*,
                   (SELECT COUNT(*) FROM members m WHERE m.group_id = g.id) AS member_count,
                   (SELECT COUNT(*) FROM expenses e WHERE e.group_id = g.id) AS expense_count
            FROM groups g
            ORDER BY g.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def set_currency(self, group_id: int, currency: str) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE groups SET currency = ? WHERE id = ?",
            (currency.upper(), group_id),
        )
        self.conn.commit()
        return self.get_group_by_id(group_id)

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def add_members(self, group_id: int, names: list[str]) -> tuple[list[str], list[str]]:
        """Returns (added_names, already_existing_names)."""
        added: list[str] = []
        existed: list[str] = []
        now = datetime.now().isoformat(timespec="seconds")
        for raw in names:
            clean = raw.strip()
            existing = self.conn.execute(
                "SELECT name FROM members WHERE group_id = ? AND name = ? COLLATE NOCASE",
                (group_id, clean),
            ).fetchone()
            if existing:
                existed.append(existing["name"])
            else:
                self.conn.execute(
                    "INSERT INTO members (group_id, name, created_at) VALUES (?, ?, ?)",
                    (group_id, clean, now),
                )
                added.append(clean)
        self.conn.commit()
        return added, existed

    def remove_members(self, group_id: int, names: list[str]) -> tuple[list[str], list[str]]:
        """Returns (removed_names, not_found_names)."""
        removed: list[str] = []
        not_found: list[str] = []
        for raw in names:
            clean = raw.strip()
            row = self.conn.execute(
                "SELECT id, name FROM members WHERE group_id = ? AND name = ? COLLATE NOCASE",
                (group_id, clean),
            ).fetchone()
            if row:
                self.conn.execute("DELETE FROM members WHERE id = ?", (row["id"],))
                removed.append(row["name"])
            else:
                not_found.append(clean)
        self.conn.commit()
        return removed, not_found

    def list_members(self, group_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM members WHERE group_id = ? ORDER BY id ASC",
            (group_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def resolve_member_name(self, group_id: int, name: str) -> str | None:
        row = self.conn.execute(
            "SELECT name FROM members WHERE group_id = ? AND name = ? COLLATE NOCASE",
            (group_id, name.strip()),
        ).fetchone()
        return row["name"] if row else None

    # ------------------------------------------------------------------
    # Expenses & Bills
    # ------------------------------------------------------------------

    def add_expense(
        self,
        group_id: int,
        *,
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
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            """
            INSERT INTO expenses (
                group_id, kind, payer, description, subtotal,
                tax_amount, tip_amount, discount, total,
                split_mode, items_json, expense_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                kind,
                payer,
                description,
                str(subtotal),
                str(tax_amount),
                str(tip_amount),
                str(discount),
                str(total),
                split_mode,
                json.dumps(items) if items is not None else None,
                expense_date,
                now,
            ),
        )
        expense_id = cur.lastrowid
        for member_name, share_amt in shares.items():
            self.conn.execute(
                """
                INSERT INTO expense_shares (expense_id, member_name, share_amount)
                VALUES (?, ?, ?)
                """,
                (expense_id, member_name, str(share_amt)),
            )
        summary = f"{kind.capitalize()} #{expense_id}: {payer} paid {total} for '{description}'"
        self.conn.execute(
            """
            INSERT INTO action_log (group_id, action_type, record_id, summary, created_at)
            VALUES (?, 'expense', ?, ?, ?)
            """,
            (group_id, expense_id, summary, now),
        )
        self.conn.commit()
        return expense_id

    def list_expenses(self, group_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM expenses WHERE group_id = ? ORDER BY id ASC",
            (group_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            share_rows = self.conn.execute(
                "SELECT member_name, share_amount FROM expense_shares WHERE expense_id = ? ORDER BY id ASC",
                (item["id"],),
            ).fetchall()
            item["shares"] = {sr["member_name"]: Decimal(sr["share_amount"]) for sr in share_rows}
            item["subtotal"] = Decimal(item["subtotal"])
            item["tax_amount"] = Decimal(item["tax_amount"])
            item["tip_amount"] = Decimal(item["tip_amount"])
            item["discount"] = Decimal(item["discount"])
            item["total"] = Decimal(item["total"])
            item["items"] = json.loads(item["items_json"]) if item["items_json"] else None
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # Settlements
    # ------------------------------------------------------------------

    def add_settlement(
        self,
        group_id: int,
        *,
        from_member: str,
        to_member: str,
        amount: Decimal,
        note: str,
        settle_date: str,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute(
            """
            INSERT INTO settlements (
                group_id, from_member, to_member, amount, note, settle_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (group_id, from_member, to_member, str(amount), note, settle_date, now),
        )
        settle_id = cur.lastrowid
        summary = f"Settlement #{settle_id}: {from_member} -> {to_member} ({amount})"
        self.conn.execute(
            """
            INSERT INTO action_log (group_id, action_type, record_id, summary, created_at)
            VALUES (?, 'settlement', ?, ?, ?)
            """,
            (group_id, settle_id, summary, now),
        )
        self.conn.commit()
        return settle_id

    def list_settlements(self, group_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM settlements WHERE group_id = ? ORDER BY id ASC",
            (group_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["amount"] = Decimal(item["amount"])
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # Undo & Reset
    # ------------------------------------------------------------------

    def undo_last_action(self, group_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT * FROM action_log WHERE group_id = ? ORDER BY id DESC LIMIT 1",
            (group_id,),
        ).fetchone()
        if not row:
            return None

        if row["action_type"] == "expense":
            self.conn.execute("DELETE FROM expenses WHERE id = ?", (row["record_id"],))
        elif row["action_type"] == "settlement":
            self.conn.execute("DELETE FROM settlements WHERE id = ?", (row["record_id"],))

        self.conn.execute("DELETE FROM action_log WHERE id = ?", (row["id"],))
        self.conn.commit()
        return row["summary"]

    def reset_group(self, group_id: int) -> None:
        self.conn.execute("DELETE FROM expenses WHERE group_id = ?", (group_id,))
        self.conn.execute("DELETE FROM settlements WHERE group_id = ?", (group_id,))
        self.conn.execute("DELETE FROM action_log WHERE group_id = ?", (group_id,))
        self.conn.execute("DELETE FROM members WHERE group_id = ?", (group_id,))
        self.conn.commit()
