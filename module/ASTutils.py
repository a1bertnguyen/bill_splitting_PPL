"""
Abstract Syntax Tree (AST) node classes ("Ops") for SplitLang.

Each Op represents the distilled semantic meaning of a SplitLang statement
after the Visitor strips syntactic sugar (punctuation, optional keywords, etc.).
Each Op implements:
  - action(context) : runs deterministic domain logic & updates SQLite DB
  - to_dict()       : returns structured payload for UI / API / tests
  - pretty_ast()    : returns an indented tree string for the PPL Inspector
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from module.Database import Database
from module.utilFunction import (
    HELP_TEXT,
    SemanticError,
    compute_balances,
    compute_bill_shares,
    compute_expense_shares,
    compute_optimal_settlements,
    format_money,
    quantize_money,
    resolve_member_strict,
    today_str,
)


@dataclass
class ExecutionContext:
    """Mutable session state shared across statements in a SplitLang session."""

    db: Database
    active_group_id: int

    @property
    def group(self) -> dict[str, Any]:
        return self.db.get_group_by_id(self.active_group_id)

    @property
    def currency(self) -> str:
        return self.group["currency"]


class BaseOp:
    """Abstract base class for all SplitLang AST Command Ops."""

    op_name: str = "BaseOp"

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}{self.__class__.__name__}()"


# ============================================================================
# 1. Group, Currency & Member Ops
# ============================================================================


@dataclass
class GroupOp(BaseOp):
    name: str
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        existed = ctx.db.get_group_by_name(self.name) is not None
        grp = ctx.db.ensure_group(self.name)
        ctx.active_group_id = grp["id"]
        status = "Switched to" if existed else "Created and switched to"
        self.result = {
            "group": grp,
            "message": f"{status} group '{grp['name']}' (currency: {grp['currency']}).",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "GroupOp", "name": self.name, "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}GroupOp(name={self.name!r})"


@dataclass
class CurrencyOp(BaseOp):
    currency: str
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        grp = ctx.db.set_currency(ctx.active_group_id, self.currency)
        self.result = {
            "group": grp,
            "message": f"Currency for group '{grp['name']}' set to {grp['currency']}.",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "CurrencyOp", "currency": self.currency, "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}CurrencyOp(currency={self.currency!r})"


@dataclass
class MemberOp(BaseOp):
    verb: str  # 'add' or 'remove'
    members: list[str]
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        if self.verb == "add":
            added, existed = ctx.db.add_members(ctx.active_group_id, self.members)
            parts: list[str] = []
            if added:
                parts.append(f"Added member(s): {', '.join(added)}")
            if existed:
                parts.append(f"Already in group: {', '.join(existed)}")
            msg = ". ".join(parts) + "."
            self.result = {
                "added": added,
                "existed": existed,
                "all_members": ctx.db.list_members(ctx.active_group_id),
                "message": msg,
            }
        else:
            removed, not_found = ctx.db.remove_members(ctx.active_group_id, self.members)
            parts = []
            if removed:
                parts.append(f"Removed member(s): {', '.join(removed)}")
            if not_found:
                parts.append(f"Not found: {', '.join(not_found)}")
            msg = ". ".join(parts) + "."
            self.result = {
                "removed": removed,
                "not_found": not_found,
                "all_members": ctx.db.list_members(ctx.active_group_id),
                "message": msg,
            }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "MemberOp",
            "verb": self.verb,
            "members": self.members,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}MemberOp(verb={self.verb!r}, members={self.members!r})"


# ============================================================================
# 2. Expense & Itemized Bill Ops
# ============================================================================


@dataclass
class ExpenseOp(BaseOp):
    payer: str
    amount: Decimal
    description: str
    split_spec: dict[str, Any]
    modifiers: list[dict[str, Any]] = field(default_factory=list)
    expense_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        canonical_payer = resolve_member_strict(ctx.db, ctx.active_group_id, self.payer)
        mod_calc, shares, split_mode = compute_expense_shares(
            ctx.db,
            ctx.active_group_id,
            currency,
            self.amount,
            self.split_spec,
            self.modifiers,
        )
        exp_date = self.expense_date or today_str()
        exp_id = ctx.db.add_expense(
            ctx.active_group_id,
            kind="expense",
            payer=canonical_payer,
            description=self.description,
            subtotal=mod_calc.subtotal,
            tax_amount=mod_calc.tax_amount,
            tip_amount=mod_calc.tip_amount,
            discount=mod_calc.discount_amount,
            total=mod_calc.final_total,
            split_mode=split_mode,
            shares=shares,
            expense_date=exp_date,
        )
        share_str = ", ".join(
            f"{m}: {format_money(amt, currency)}" for m, amt in shares.items()
        )
        mod_notes: list[str] = []
        if mod_calc.discount_amount > 0:
            mod_notes.append(f"discount -{format_money(mod_calc.discount_amount, currency)}")
        if mod_calc.tax_amount > 0:
            mod_notes.append(f"tax +{format_money(mod_calc.tax_amount, currency)}")
        if mod_calc.tip_amount > 0:
            mod_notes.append(f"tip +{format_money(mod_calc.tip_amount, currency)}")
        mod_suffix = f" ({', '.join(mod_notes)})" if mod_notes else ""

        msg = (
            f"Recorded Expense #{exp_id}: {canonical_payer} paid "
            f"{format_money(mod_calc.final_total, currency)}{mod_suffix} "
            f"for '{self.description}' [{split_mode}] on {exp_date}.\n"
            f"  Shares -> {share_str}"
        )
        self.result = {
            "expense_id": exp_id,
            "payer": canonical_payer,
            "description": self.description,
            "subtotal": str(mod_calc.subtotal),
            "discount": str(mod_calc.discount_amount),
            "tax": str(mod_calc.tax_amount),
            "tip": str(mod_calc.tip_amount),
            "total": str(mod_calc.final_total),
            "split_mode": split_mode,
            "shares": {k: str(v) for k, v in shares.items()},
            "date": exp_date,
            "message": msg,
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ExpenseOp",
            "payer": self.payer,
            "amount": str(self.amount),
            "description": self.description,
            "split_spec": self._serializable_split(),
            "modifiers": self._serializable_modifiers(),
            "date": self.expense_date,
            "result": self.result,
        }

    def _serializable_split(self) -> dict[str, Any]:
        out = dict(self.split_spec)
        if "allocations" in out:
            out["allocations"] = [(p, str(v)) for p, v in out["allocations"]]
        return out

    def _serializable_modifiers(self) -> list[dict[str, Any]]:
        return [
            {**m, "value": str(m["value"])}
            for m in self.modifiers
        ]

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [
            f"{pad}ExpenseOp(",
            f"{pad}  payer={self.payer!r},",
            f"{pad}  amount={str(self.amount)},",
            f"{pad}  description={self.description!r},",
            f"{pad}  split={self._serializable_split()!r},",
        ]
        if self.modifiers:
            lines.append(f"{pad}  modifiers={self._serializable_modifiers()!r},")
        if self.expense_date:
            lines.append(f"{pad}  date={self.expense_date!r},")
        lines.append(f"{pad})")
        return "\n".join(lines)


@dataclass
class BillOp(BaseOp):
    title: str
    payer: str
    items: list[dict[str, Any]]
    modifiers: list[dict[str, Any]] = field(default_factory=list)
    bill_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        canonical_payer = resolve_member_strict(ctx.db, ctx.active_group_id, self.payer)
        mod_calc, shares, resolved_items = compute_bill_shares(
            ctx.db,
            ctx.active_group_id,
            currency,
            self.items,
            self.modifiers,
        )
        b_date = self.bill_date or today_str()
        exp_id = ctx.db.add_expense(
            ctx.active_group_id,
            kind="bill",
            payer=canonical_payer,
            description=self.title,
            subtotal=mod_calc.subtotal,
            tax_amount=mod_calc.tax_amount,
            tip_amount=mod_calc.tip_amount,
            discount=mod_calc.discount_amount,
            total=mod_calc.final_total,
            split_mode="itemized",
            shares=shares,
            expense_date=b_date,
            items=resolved_items,
        )
        lines = [
            f"Recorded Itemized Bill #{exp_id} '{self.title}' paid by {canonical_payer} on {b_date}:",
            f"  Subtotal : {format_money(mod_calc.subtotal, currency)}",
        ]
        if mod_calc.discount_amount > 0:
            lines.append(f"  Discount : -{format_money(mod_calc.discount_amount, currency)}")
        if mod_calc.tax_amount > 0:
            lines.append(f"  Tax      : +{format_money(mod_calc.tax_amount, currency)}")
        if mod_calc.tip_amount > 0:
            lines.append(f"  Tip      : +{format_money(mod_calc.tip_amount, currency)}")
        lines.append(f"  Total    : {format_money(mod_calc.final_total, currency)}")
        lines.append("  Items    :")
        for it in resolved_items:
            lines.append(
                f"    - {it['name']}: {format_money(Decimal(it['amount']), currency)} "
                f"({', '.join(it['consumers'])})"
            )
        share_str = ", ".join(
            f"{m}: {format_money(amt, currency)}" for m, amt in shares.items()
        )
        lines.append(f"  Shares   -> {share_str}")

        self.result = {
            "expense_id": exp_id,
            "title": self.title,
            "payer": canonical_payer,
            "subtotal": str(mod_calc.subtotal),
            "discount": str(mod_calc.discount_amount),
            "tax": str(mod_calc.tax_amount),
            "tip": str(mod_calc.tip_amount),
            "total": str(mod_calc.final_total),
            "items": resolved_items,
            "shares": {k: str(v) for k, v in shares.items()},
            "date": b_date,
            "message": "\n".join(lines),
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BillOp",
            "title": self.title,
            "payer": self.payer,
            "items": [{**it, "amount": str(it["amount"])} for it in self.items],
            "modifiers": [{**m, "value": str(m["value"])} for m in self.modifiers],
            "date": self.bill_date,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [
            f"{pad}BillOp(",
            f"{pad}  title={self.title!r},",
            f"{pad}  payer={self.payer!r},",
            f"{pad}  items=[",
        ]
        for it in self.items:
            target = (
                f"ALL(excluding={it.get('excluding', [])})"
                if it["for_all"]
                else repr(it["consumers"])
            )
            lines.append(f"{pad}    BillItem(name={it['name']!r}, amount={it['amount']}, for={target}),")
        lines.append(f"{pad}  ],")
        if self.modifiers:
            mods = [{**m, "value": str(m["value"])} for m in self.modifiers]
            lines.append(f"{pad}  modifiers={mods!r},")
        lines.append(f"{pad})")
        return "\n".join(lines)


# ============================================================================
# 3. Settlement Ops
# ============================================================================


@dataclass
class SettleOp(BaseOp):
    from_member: str
    to_member: str
    amount: Decimal
    note: str = ""
    settle_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        src = resolve_member_strict(ctx.db, ctx.active_group_id, self.from_member)
        dst = resolve_member_strict(ctx.db, ctx.active_group_id, self.to_member)
        if src.lower() == dst.lower():
            raise SemanticError(f"Cannot record a settlement from '{src}' to themselves.")
        amt = quantize_money(self.amount, currency)
        if amt <= 0:
            raise SemanticError("Settlement amount must be strictly greater than 0.")

        s_date = self.settle_date or today_str()
        sid = ctx.db.add_settlement(
            ctx.active_group_id,
            from_member=src,
            to_member=dst,
            amount=amt,
            note=self.note,
            settle_date=s_date,
        )
        note_part = f" ({self.note})" if self.note else ""
        msg = (
            f"Recorded Settlement #{sid}: {src} paid {dst} "
            f"{format_money(amt, currency)}{note_part} on {s_date}."
        )
        self.result = {
            "settlement_id": sid,
            "from": src,
            "to": dst,
            "amount": str(amt),
            "note": self.note,
            "date": s_date,
            "message": msg,
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SettleOp",
            "from": self.from_member,
            "to": self.to_member,
            "amount": str(self.amount),
            "note": self.note,
            "date": self.settle_date,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return (
            f"{pad}SettleOp(from={self.from_member!r}, to={self.to_member!r}, "
            f"amount={self.amount}, note={self.note!r})"
        )


@dataclass
class SettleUpOp(BaseOp):
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        balances = compute_balances(ctx.db, ctx.active_group_id)
        transfers = compute_optimal_settlements(balances, currency)
        if not transfers:
            msg = f"All settled up in group '{ctx.group['name']}'! No transfers needed."
        else:
            lines = [
                f"Optimal Settlement Plan for '{ctx.group['name']}' "
                f"({len(transfers)} transfer{'s' if len(transfers) != 1 else ''}):"
            ]
            for i, tr in enumerate(transfers, 1):
                lines.append(f"  {i}. {tr['from']} -> {tr['to']}: {tr['formatted']}")
            msg = "\n".join(lines)
        self.result = {
            "transfers": [
                {**t, "amount": str(t["amount"])} for t in transfers
            ],
            "message": msg,
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "SettleUpOp", "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}SettleUpOp()"


# ============================================================================
# 4. Query & Report Ops
# ============================================================================


@dataclass
class QueryOp(BaseOp):
    query_kind: str  # members, expenses, balances, summary, settlements, groups, who_owes_whom, how_much_owes, person_balance
    target_member: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        grp = ctx.group
        currency = grp["currency"]

        if self.query_kind == "members":
            members = ctx.db.list_members(ctx.active_group_id)
            msg = (
                f"Members in '{grp['name']}' ({len(members)}): {', '.join(members)}"
                if members
                else f"No members in '{grp['name']}' yet."
            )
            self.result = {"members": members, "message": msg}

        elif self.query_kind == "groups":
            groups = ctx.db.list_groups()
            lines = ["Groups:"]
            for g in groups:
                marker = " *active*" if g["id"] == ctx.active_group_id else ""
                lines.append(
                    f"  - {g['name']} ({g['currency']}, "
                    f"{g['member_count']} members, {g['expense_count']} expenses){marker}"
                )
            self.result = {"groups": groups, "message": "\n".join(lines)}

        elif self.query_kind == "expenses":
            expenses = ctx.db.list_expenses(ctx.active_group_id)
            if not expenses:
                msg = f"No expenses recorded in '{grp['name']}' yet."
            else:
                lines = [f"Expenses in '{grp['name']}' ({len(expenses)}):"]
                for e in expenses:
                    tag = "BILL" if e["kind"] == "bill" else e["split_mode"].upper()
                    lines.append(
                        f"  #{e['id']} [{e['expense_date']}] {e['payer']} paid "
                        f"{format_money(e['total'], currency)} for '{e['description']}' ({tag})"
                    )
                msg = "\n".join(lines)
            self.result = {
                "expenses": [
                    {
                        "id": e["id"],
                        "kind": e["kind"],
                        "payer": e["payer"],
                        "description": e["description"],
                        "total": str(e["total"]),
                        "split_mode": e["split_mode"],
                        "date": e["expense_date"],
                        "shares": {k: str(v) for k, v in e["shares"].items()},
                    }
                    for e in expenses
                ],
                "message": msg,
            }

        elif self.query_kind == "balances":
            balances = compute_balances(ctx.db, ctx.active_group_id)
            if not balances:
                msg = f"No members in '{grp['name']}' yet."
            else:
                lines = [f"Balances in '{grp['name']}':"]
                for b in balances:
                    net_val = b["net"]
                    if net_val > 0:
                        status = f"+{format_money(net_val, currency)} (gets back)"
                    elif net_val < 0:
                        status = f"{format_money(net_val, currency)} (owes)"
                    else:
                        status = f"{format_money(Decimal('0'), currency)} (settled)"
                    lines.append(
                        f"  - {b['member']}: Paid {format_money(b['paid'], currency)} | "
                        f"Share {format_money(b['owed'], currency)} | Net {status}"
                    )
                msg = "\n".join(lines)
            self.result = {
                "balances": [
                    {
                        "member": b["member"],
                        "paid": str(b["paid"]),
                        "owed": str(b["owed"]),
                        "net": str(b["net"]),
                    }
                    for b in balances
                ],
                "message": msg,
            }

        elif self.query_kind in ("settlements", "who_owes_whom"):
            balances = compute_balances(ctx.db, ctx.active_group_id)
            transfers = compute_optimal_settlements(balances, currency)
            if not transfers:
                msg = f"Everyone is settled up in '{grp['name']}'!"
            else:
                lines = [f"Who Owes Whom in '{grp['name']}' (Optimal {len(transfers)} transfer(s)):"]
                for i, tr in enumerate(transfers, 1):
                    lines.append(f"  {i}. {tr['from']} owes {tr['to']} {tr['formatted']}")
                msg = "\n".join(lines)
            self.result = {
                "transfers": [{**t, "amount": str(t["amount"])} for t in transfers],
                "message": msg,
            }

        elif self.query_kind == "summary":
            members = ctx.db.list_members(ctx.active_group_id)
            expenses = ctx.db.list_expenses(ctx.active_group_id)
            settlements = ctx.db.list_settlements(ctx.active_group_id)
            balances = compute_balances(ctx.db, ctx.active_group_id)
            transfers = compute_optimal_settlements(balances, currency)
            total_spent = sum((e["total"] for e in expenses), Decimal("0"))
            avg_per_member = (total_spent / len(members)) if members else Decimal("0")
            top_payer = max(balances, key=lambda b: b["paid"]) if balances else None
            lines = [
                f"Summary for '{grp['name']}' ({currency}):",
                f"  Members        : {len(members)} ({', '.join(members) if members else 'none'})",
                f"  Expenses/Bills : {len(expenses)}",
                f"  Repayments     : {len(settlements)}",
                f"  Total Spent    : {format_money(total_spent, currency)}",
                f"  Avg per Member : {format_money(avg_per_member, currency)}",
            ]
            if top_payer and top_payer["paid"] > 0:
                lines.append(
                    f"  Top Payer      : {top_payer['member']} "
                    f"({format_money(top_payer['paid'], currency)})"
                )
            lines.append(f"  Transfers Left : {len(transfers)}")
            self.result = {
                "total_spent": str(total_spent),
                "average_per_member": str(avg_per_member),
                "expense_count": len(expenses),
                "member_count": len(members),
                "transfers_remaining": len(transfers),
                "message": "\n".join(lines),
            }

        elif self.query_kind in ("how_much_owes", "person_balance"):
            assert self.target_member is not None
            canonical = resolve_member_strict(ctx.db, ctx.active_group_id, self.target_member)
            balances = compute_balances(ctx.db, ctx.active_group_id)
            transfers = compute_optimal_settlements(balances, currency)
            person_row = next(b for b in balances if b["member"].lower() == canonical.lower())
            net = person_row["net"]
            outgoing = [t for t in transfers if t["from"].lower() == canonical.lower()]
            incoming = [t for t in transfers if t["to"].lower() == canonical.lower()]

            lines = [
                f"Balance for {canonical} in '{grp['name']}':",
                f"  Paid  : {format_money(person_row['paid'], currency)}",
                f"  Share : {format_money(person_row['owed'], currency)}",
            ]
            if net < 0:
                lines.append(f"  Status: Owes {format_money(-net, currency)} total")
                for t in outgoing:
                    lines.append(f"    -> Pay {t['to']} {t['formatted']}")
            elif net > 0:
                lines.append(f"  Status: Owed {format_money(net, currency)} total")
                for t in incoming:
                    lines.append(f"    <- Receive {t['formatted']} from {t['from']}")
            else:
                lines.append("  Status: All settled up!")

            self.result = {
                "member": canonical,
                "paid": str(person_row["paid"]),
                "owed": str(person_row["owed"]),
                "net": str(net),
                "outgoing": [{**t, "amount": str(t["amount"])} for t in outgoing],
                "incoming": [{**t, "amount": str(t["amount"])} for t in incoming],
                "message": "\n".join(lines),
            }

        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "QueryOp",
            "query_kind": self.query_kind,
            "target_member": self.target_member,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        if self.target_member:
            return f"{pad}QueryOp(kind={self.query_kind!r}, member={self.target_member!r})"
        return f"{pad}QueryOp(kind={self.query_kind!r})"


# ============================================================================
# 5. Control Ops
# ============================================================================


@dataclass
class ControlOp(BaseOp):
    command: str  # undo, reset, clear, help
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        if self.command == "undo":
            undone = ctx.db.undo_last_action(ctx.active_group_id)
            if undone:
                msg = f"Undid last action: {undone}"
            else:
                msg = "Nothing to undo in this group."
            self.result = {"undone": undone, "message": msg}
        elif self.command == "reset":
            grp_name = ctx.group["name"]
            ctx.db.reset_group(ctx.active_group_id)
            self.result = {"message": f"Reset group '{grp_name}' (cleared members, expenses, settlements)."}
        elif self.command == "clear":
            self.result = {"clear_ui": True, "message": "Console cleared."}
        elif self.command == "help":
            self.result = {"message": HELP_TEXT}
        else:
            raise SemanticError(f"Unknown control command: {self.command}")
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "ControlOp", "command": self.command, "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}ControlOp(command={self.command!r})"
