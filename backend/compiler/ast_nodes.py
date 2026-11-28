"""
SplitLang v2.0 — Typed Expression AST, Symbol Table, and Command Ops.

Demonstrates core Principles of Programming Languages concepts:
  - Dimensional Type System : MONEY, SCALAR, PERCENT, MEMBER_SET
  - Symbol Table (Environment): `let` typed bindings + `rule` named split abstractions
  - Set Algebra on Members  : `all`, `[a, b]`, union (`+`), difference (`-`)
  - Runtime Assertions      : `assert balanced` verifies zero-sum ledger invariant
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from backend.repositories.database import Database
from backend.services.split_math import (
    HELP_TEXT,
    SemanticError,
    compute_balances,
    compute_bill_shares,
    compute_expense_shares,
    compute_optimal_settlements,
    format_money,
    quantize_money,
    resolve_member_strict,
    resolve_unique_members,
    today_str,
)


class SplitTypeError(SemanticError):
    """Raised when an expression or clause violates SplitLang's static/dimensional type rules."""


class ValueType(str, Enum):
    MONEY = "MONEY"
    SCALAR = "SCALAR"
    PERCENT = "PERCENT"
    MEMBER_SET = "MEMBER_SET"


@dataclass(frozen=True)
class TypedValue:
    kind: ValueType
    value: Any  # Decimal or list[str]

    def format_display(self, currency: str = "VND") -> str:
        if self.kind == ValueType.MONEY:
            return format_money(self.value, currency)
        if self.kind == ValueType.PERCENT:
            return f"{self.value}%"
        if self.kind == ValueType.MEMBER_SET:
            return "[" + ", ".join(self.value) + "]"
        return str(self.value)


@dataclass
class ExecutionContext:
    """Mutable session state holding DB handle, Row-Level owner, active group, and Symbol Table."""

    db: Database
    owner_user_id: int
    active_group_id: int
    env: dict[str, TypedValue] = field(default_factory=dict)
    rules: dict[str, "SplitNode"] = field(default_factory=dict)

    @property
    def group(self) -> dict[str, Any]:
        return self.db.get_group_by_id(self.active_group_id, owner_user_id=self.owner_user_id)

    @property
    def currency(self) -> str:
        return self.group["currency"]


# ============================================================================
# EXPRESSION AST NODES (Typed Evaluator with Dimensional Safety)
# ============================================================================


class ExprNode:
    def eval(self, ctx: ExecutionContext) -> TypedValue:
        raise NotImplementedError

    def pretty(self) -> str:
        return repr(self)


@dataclass(frozen=True)
class MoneyLit(ExprNode):
    value: Decimal

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        return TypedValue(ValueType.MONEY, self.value)

    def pretty(self) -> str:
        return f"Money({self.value})"


@dataclass(frozen=True)
class ScalarLit(ExprNode):
    value: Decimal

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        return TypedValue(ValueType.SCALAR, self.value)

    def pretty(self) -> str:
        return f"Scalar({self.value})"


@dataclass(frozen=True)
class PercentLit(ExprNode):
    value: Decimal

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        return TypedValue(ValueType.PERCENT, self.value)

    def pretty(self) -> str:
        return f"Percent({self.value}%)"


@dataclass(frozen=True)
class SetLit(ExprNode):
    members: tuple[str, ...]

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        resolved = resolve_unique_members(
            ctx.db, ctx.active_group_id, list(self.members), owner_user_id=ctx.owner_user_id
        )
        return TypedValue(ValueType.MEMBER_SET, resolved)

    def pretty(self) -> str:
        return f"Set([{', '.join(self.members)}])"


@dataclass(frozen=True)
class AllMembersLit(ExprNode):
    def eval(self, ctx: ExecutionContext) -> TypedValue:
        members = ctx.db.list_members(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
        return TypedValue(ValueType.MEMBER_SET, members)

    def pretty(self) -> str:
        return "AllMembers"


@dataclass(frozen=True)
class VarRef(ExprNode):
    name: str

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        if self.name not in ctx.env:
            raise SemanticError(
                f"Undefined variable '{self.name}'. Declare it first with 'let {self.name} = ...'."
            )
        return ctx.env[self.name]

    def pretty(self) -> str:
        return f"Var({self.name})"


@dataclass(frozen=True)
class UnaryNeg(ExprNode):
    operand: ExprNode

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        val = self.operand.eval(ctx)
        if val.kind == ValueType.MEMBER_SET:
            raise SplitTypeError("Type Error: Cannot apply unary '-' to MEMBER_SET.")
        return TypedValue(val.kind, -val.value)

    def pretty(self) -> str:
        return f"Neg({self.operand.pretty()})"


@dataclass(frozen=True)
class BinaryOp(ExprNode):
    op: str  # '+', '-', '*', '/'
    left: ExprNode
    right: ExprNode

    def eval(self, ctx: ExecutionContext) -> TypedValue:
        lv = self.left.eval(ctx)
        rv = self.right.eval(ctx)
        lt, rt = lv.kind, rv.kind

        if self.op == "+":
            if lt == rt and lt in (ValueType.MONEY, ValueType.SCALAR, ValueType.PERCENT):
                return TypedValue(lt, lv.value + rv.value)
            if lt == ValueType.MEMBER_SET and rt == ValueType.MEMBER_SET:
                seen = {m.lower() for m in lv.value}
                union = list(lv.value) + [m for m in rv.value if m.lower() not in seen]
                return TypedValue(ValueType.MEMBER_SET, union)
            raise SplitTypeError(
                f"Type Error: Cannot apply '+' to {lt.value} and {rt.value}."
            )

        if self.op == "-":
            if lt == rt and lt in (ValueType.MONEY, ValueType.SCALAR, ValueType.PERCENT):
                return TypedValue(lt, lv.value - rv.value)
            if lt == ValueType.MEMBER_SET and rt == ValueType.MEMBER_SET:
                removed = {m.lower() for m in rv.value}
                diff = [m for m in lv.value if m.lower() not in removed]
                return TypedValue(ValueType.MEMBER_SET, diff)
            raise SplitTypeError(
                f"Type Error: Cannot apply '-' to {lt.value} and {rt.value}."
            )

        if self.op == "*":
            if lt == ValueType.MONEY and rt == ValueType.SCALAR:
                return TypedValue(ValueType.MONEY, lv.value * rv.value)
            if lt == ValueType.SCALAR and rt == ValueType.MONEY:
                return TypedValue(ValueType.MONEY, lv.value * rv.value)
            if lt == ValueType.SCALAR and rt == ValueType.SCALAR:
                return TypedValue(ValueType.SCALAR, lv.value * rv.value)
            if lt == ValueType.MONEY and rt == ValueType.PERCENT:
                return TypedValue(ValueType.MONEY, (lv.value * rv.value) / Decimal("100"))
            if lt == ValueType.PERCENT and rt == ValueType.MONEY:
                return TypedValue(ValueType.MONEY, (rv.value * lv.value) / Decimal("100"))
            if lt == ValueType.PERCENT and rt == ValueType.SCALAR:
                return TypedValue(ValueType.PERCENT, lv.value * rv.value)
            if lt == ValueType.SCALAR and rt == ValueType.PERCENT:
                return TypedValue(ValueType.PERCENT, lv.value * rv.value)
            if lt == ValueType.MONEY and rt == ValueType.MONEY:
                raise SplitTypeError("Type Error: Cannot multiply MONEY by MONEY (dimensional violation).")
            raise SplitTypeError(f"Type Error: Cannot apply '*' to {lt.value} and {rt.value}.")

        if self.op == "/":
            if rt == ValueType.MEMBER_SET or lt == ValueType.MEMBER_SET:
                raise SplitTypeError("Type Error: Operator '/' is not supported for MEMBER_SET.")
            if rv.value == 0:
                raise SemanticError("Division by zero in expression.")
            if lt == ValueType.MONEY and rt == ValueType.SCALAR:
                return TypedValue(ValueType.MONEY, lv.value / rv.value)
            if lt == ValueType.SCALAR and rt == ValueType.SCALAR:
                return TypedValue(ValueType.SCALAR, lv.value / rv.value)
            if lt == ValueType.MONEY and rt == ValueType.MONEY:
                return TypedValue(ValueType.SCALAR, lv.value / rv.value)
            if lt == ValueType.PERCENT and rt == ValueType.SCALAR:
                return TypedValue(ValueType.PERCENT, lv.value / rv.value)
            raise SplitTypeError(f"Type Error: Cannot apply '/' to {lt.value} and {rt.value}.")

        raise SemanticError(f"Unknown binary operator: {self.op}")

    def pretty(self) -> str:
        return f"BinOp({self.op!r}, {self.left.pretty()}, {self.right.pretty()})"


def _expect_money(tv: TypedValue, context_label: str) -> Decimal:
    if tv.kind in (ValueType.MONEY, ValueType.SCALAR):
        return Decimal(tv.value)
    raise SplitTypeError(
        f"Type Error: {context_label} expects MONEY or SCALAR, got {tv.kind.value}."
    )


def _expect_percent(tv: TypedValue, context_label: str) -> Decimal:
    if tv.kind == ValueType.PERCENT:
        return Decimal(tv.value)
    raise SplitTypeError(f"Type Error: {context_label} expects PERCENT, got {tv.kind.value}.")


def _expect_scalar(tv: TypedValue, context_label: str) -> Decimal:
    if tv.kind == ValueType.SCALAR:
        return Decimal(tv.value)
    raise SplitTypeError(f"Type Error: {context_label} expects SCALAR, got {tv.kind.value}.")


def _expect_member_set(tv: TypedValue, context_label: str) -> list[str]:
    if tv.kind == ValueType.MEMBER_SET:
        return list(tv.value)
    raise SplitTypeError(f"Type Error: {context_label} expects MEMBER_SET, got {tv.kind.value}.")


def _eval_modifier(kind: str, expr: ExprNode, ctx: ExecutionContext) -> dict[str, Any]:
    tv = expr.eval(ctx)
    if tv.kind == ValueType.PERCENT:
        return {"kind": kind, "is_percent": True, "value": tv.value}
    if tv.kind in (ValueType.MONEY, ValueType.SCALAR):
        return {"kind": kind, "is_percent": False, "value": tv.value}
    raise SplitTypeError(
        f"Type Error: Modifier '{kind}' expects PERCENT or MONEY, got {tv.kind.value}."
    )


# ============================================================================
# SPLIT SPECIFICATION AST NODES
# ============================================================================


@dataclass
class SplitNode:
    mode: str  # 'equal', 'exact', 'percent', 'ratio', 'rule_ref'
    target_expr: ExprNode | None = None
    alloc_exprs: list[tuple[str, ExprNode]] = field(default_factory=list)
    rule_name: str | None = None

    def resolve(self, ctx: ExecutionContext) -> dict[str, Any]:
        if self.mode == "rule_ref":
            assert self.rule_name is not None
            if self.rule_name not in ctx.rules:
                raise SemanticError(
                    f"Undefined split rule '{self.rule_name}'. Declare it first with 'rule {self.rule_name} = ...'."
                )
            return ctx.rules[self.rule_name].resolve(ctx)

        if self.mode == "equal":
            if self.target_expr is None:
                return {"mode": "equal", "among": None, "excluding": None}
            participants = _expect_member_set(self.target_expr.eval(ctx), "equal(...)")
            if not participants:
                raise SemanticError("Split target set is empty (0 participants).")
            return {"mode": "equal", "among": participants, "excluding": None}

        if self.mode == "exact":
            if not self.alloc_exprs:
                raise SemanticError("exact { ... } split requires at least one allocation.")
            allocs = [(m, _expect_money(e.eval(ctx), f"exact[{m}]")) for m, e in self.alloc_exprs]
            return {"mode": "exact", "allocations": allocs}

        if self.mode == "percent":
            if not self.alloc_exprs:
                raise SemanticError("percent { ... } split requires at least one allocation.")
            allocs = [(m, _expect_percent(e.eval(ctx), f"percent[{m}]")) for m, e in self.alloc_exprs]
            return {"mode": "percent", "allocations": allocs}

        if self.mode == "ratio":
            if not self.alloc_exprs:
                raise SemanticError("ratio { ... } split requires at least one allocation.")
            allocs = [(m, _expect_scalar(e.eval(ctx), f"ratio[{m}]")) for m, e in self.alloc_exprs]
            return {"mode": "ratio", "allocations": allocs}

        raise SemanticError(f"Unsupported split node: {self.mode}")

    def pretty(self) -> str:
        if self.mode == "rule_ref":
            return f"RuleRef({self.rule_name!r})"
        if self.mode == "equal":
            return f"Equal({self.target_expr.pretty() if self.target_expr else 'AllMembers'})"
        entries = ", ".join(f"{m}: {e.pretty()}" for m, e in self.alloc_exprs)
        return f"{self.mode.capitalize()}({{{entries}}})"


# ============================================================================
# COMMAND AST NODES ("Ops")
# ============================================================================


class BaseOp:
    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}{self.__class__.__name__}()"


@dataclass
class WorkspaceOp(BaseOp):
    name: str
    currency: str | None = None
    members: list[str] | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        existed = ctx.db.get_group_by_name(self.name, owner_user_id=ctx.owner_user_id) is not None
        grp = ctx.db.ensure_group(
            self.name,
            currency=self.currency or "VND",
            owner_user_id=ctx.owner_user_id,
        )
        ctx.active_group_id = grp["id"]
        if self.currency:
            grp = ctx.db.set_currency(grp["id"], self.currency, owner_user_id=ctx.owner_user_id)

        added: list[str] = []
        if self.members:
            added, _ = ctx.db.add_members(grp["id"], self.members, owner_user_id=ctx.owner_user_id)

        status = "Switched to" if existed else "Created"
        parts = [f"{status} workspace '{grp['name']}' (currency: {grp['currency']})."]
        if added:
            parts.append(f"Added members: {', '.join(added)}.")
        self.result = {
            "group": {"id": grp["id"], "name": grp["name"], "currency": grp["currency"]},
            "added_members": added,
            "message": " ".join(parts),
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "WorkspaceOp",
            "name": self.name,
            "currency": self.currency,
            "members": self.members,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        return f"{pad}WorkspaceOp(name={self.name!r}, currency={self.currency!r}, members={self.members!r})"


@dataclass
class CurrencyOp(BaseOp):
    currency: str
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        grp = ctx.db.set_currency(ctx.active_group_id, self.currency, owner_user_id=ctx.owner_user_id)
        self.result = {
            "group": {"id": grp["id"], "name": grp["name"], "currency": grp["currency"]},
            "message": f"Currency for workspace '{grp['name']}' set to {grp['currency']}.",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "CurrencyOp", "currency": self.currency, "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}CurrencyOp(currency={self.currency!r})"


@dataclass
class MemberOp(BaseOp):
    verb: str  # 'add' or 'remove'
    members: list[str]
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        if self.verb == "add":
            added, existed = ctx.db.add_members(
                ctx.active_group_id, self.members, owner_user_id=ctx.owner_user_id
            )
            parts: list[str] = []
            if added:
                parts.append(f"Added member(s): {', '.join(added)}")
            if existed:
                parts.append(f"Already present: {', '.join(existed)}")
            self.result = {
                "added": added,
                "existed": existed,
                "all_members": ctx.db.list_members(ctx.active_group_id, owner_user_id=ctx.owner_user_id),
                "message": ". ".join(parts) + ".",
            }
        else:
            removed, not_found = ctx.db.remove_members(
                ctx.active_group_id, self.members, owner_user_id=ctx.owner_user_id
            )
            parts = []
            if removed:
                parts.append(f"Removed member(s): {', '.join(removed)}")
            if not_found:
                parts.append(f"Not found: {', '.join(not_found)}")
            self.result = {
                "removed": removed,
                "not_found": not_found,
                "all_members": ctx.db.list_members(ctx.active_group_id, owner_user_id=ctx.owner_user_id),
                "message": ". ".join(parts) + ".",
            }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MemberOp", "verb": self.verb, "members": self.members, "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}MemberOp(verb={self.verb!r}, members={self.members!r})"


@dataclass
class LetOp(BaseOp):
    name: str
    expr: ExprNode
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        tv = self.expr.eval(ctx)
        ctx.env[self.name] = tv
        disp = tv.format_display(ctx.currency)
        self.result = {
            "name": self.name,
            "value_type": tv.kind.value,
            "value": str(tv.value) if tv.kind != ValueType.MEMBER_SET else tv.value,
            "message": f"Bound let {self.name}: {tv.kind.value} = {disp}",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "LetOp", "name": self.name, "expr": self.expr.pretty(), "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}LetOp(name={self.name!r}, expr={self.expr.pretty()})"


@dataclass
class RuleOp(BaseOp):
    name: str
    split_node: SplitNode
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        # Eagerly validate rule expression types & members when defined
        self.split_node.resolve(ctx)
        ctx.rules[self.name] = self.split_node
        self.result = {
            "name": self.name,
            "split": self.split_node.pretty(),
            "message": f"Defined split rule '{self.name}' = {self.split_node.pretty()}",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "RuleOp",
            "name": self.name,
            "split": self.split_node.pretty(),
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}RuleOp(name={self.name!r}, split={self.split_node.pretty()})"


@dataclass
class ExpenseOp(BaseOp):
    description: str
    payer: str
    amount_expr: ExprNode
    split_node: SplitNode
    modifier_exprs: list[tuple[str, ExprNode]] = field(default_factory=list)
    expense_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        canonical_payer = resolve_member_strict(
            ctx.db, ctx.active_group_id, self.payer, owner_user_id=ctx.owner_user_id
        )
        amount_val = _expect_money(self.amount_expr.eval(ctx), "expense amount")
        split_spec = self.split_node.resolve(ctx)
        modifiers = [_eval_modifier(k, expr, ctx) for k, expr in self.modifier_exprs]

        mod_calc, shares, split_mode = compute_expense_shares(
            ctx.db,
            ctx.active_group_id,
            currency,
            amount_val,
            split_spec,
            modifiers,
            owner_user_id=ctx.owner_user_id,
        )
        exp_date = self.expense_date or today_str()
        exp_id = ctx.db.add_expense(
            ctx.active_group_id,
            owner_user_id=ctx.owner_user_id,
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
        share_str = ", ".join(f"{m}: {format_money(amt, currency)}" for m, amt in shares.items())
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
            "description": self.description,
            "payer": self.payer,
            "amount": self.amount_expr.pretty(),
            "split": self.split_node.pretty(),
            "modifiers": [(k, e.pretty()) for k, e in self.modifier_exprs],
            "date": self.expense_date,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        pad = "  " * indent
        lines = [
            f"{pad}ExpenseOp(",
            f"{pad}  title={self.description!r},",
            f"{pad}  payer={self.payer!r},",
            f"{pad}  amount={self.amount_expr.pretty()},",
            f"{pad}  split={self.split_node.pretty()},",
        ]
        if self.modifier_exprs:
            mods = ", ".join(f"{k}={e.pretty()}" for k, e in self.modifier_exprs)
            lines.append(f"{pad}  modifiers=[{mods}],")
        if self.expense_date:
            lines.append(f"{pad}  date={self.expense_date!r},")
        lines.append(f"{pad})")
        return "\n".join(lines)


@dataclass
class BillItemNode:
    name: str
    amount_expr: ExprNode
    target_expr: ExprNode

    def pretty(self) -> str:
        return f"BillItem(name={self.name!r}, amount={self.amount_expr.pretty()}, for={self.target_expr.pretty()})"


@dataclass
class BillOp(BaseOp):
    title: str
    payer: str
    items: list[BillItemNode]
    modifier_exprs: list[tuple[str, ExprNode]] = field(default_factory=list)
    bill_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        canonical_payer = resolve_member_strict(
            ctx.db, ctx.active_group_id, self.payer, owner_user_id=ctx.owner_user_id
        )
        eval_items: list[dict[str, Any]] = []
        for it in self.items:
            amt = _expect_money(it.amount_expr.eval(ctx), f"item '{it.name}' amount")
            consumers = _expect_member_set(it.target_expr.eval(ctx), f"item '{it.name}' target")
            eval_items.append(
                {"name": it.name, "amount": amt, "for_all": False, "consumers": consumers}
            )
        modifiers = [_eval_modifier(k, expr, ctx) for k, expr in self.modifier_exprs]

        mod_calc, shares, resolved_items = compute_bill_shares(
            ctx.db,
            ctx.active_group_id,
            currency,
            eval_items,
            modifiers,
            owner_user_id=ctx.owner_user_id,
        )
        b_date = self.bill_date or today_str()
        exp_id = ctx.db.add_expense(
            ctx.active_group_id,
            owner_user_id=ctx.owner_user_id,
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
        for it_res in resolved_items:
            lines.append(
                f"    - {it_res['name']}: {format_money(Decimal(it_res['amount']), currency)} "
                f"({', '.join(it_res['consumers'])})"
            )
        share_str = ", ".join(f"{m}: {format_money(amt, currency)}" for m, amt in shares.items())
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
            "items": [it.pretty() for it in self.items],
            "modifiers": [(k, e.pretty()) for k, e in self.modifier_exprs],
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
            lines.append(f"{pad}    {it.pretty()},")
        lines.append(f"{pad}  ],")
        if self.modifier_exprs:
            mods = ", ".join(f"{k}={e.pretty()}" for k, e in self.modifier_exprs)
            lines.append(f"{pad}  modifiers=[{mods}],")
        lines.append(f"{pad})")
        return "\n".join(lines)


@dataclass
class TransferOp(BaseOp):
    from_member: str
    to_member: str
    amount_expr: ExprNode
    note: str = ""
    settle_date: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        currency = ctx.currency
        src = resolve_member_strict(
            ctx.db, ctx.active_group_id, self.from_member, owner_user_id=ctx.owner_user_id
        )
        dst = resolve_member_strict(
            ctx.db, ctx.active_group_id, self.to_member, owner_user_id=ctx.owner_user_id
        )
        if src.lower() == dst.lower():
            raise SemanticError(f"Cannot transfer from '{src}' to themselves.")
        amt = quantize_money(_expect_money(self.amount_expr.eval(ctx), "transfer amount"), currency)
        if amt <= 0:
            raise SemanticError("Transfer amount must be strictly greater than 0.")

        s_date = self.settle_date or today_str()
        sid = ctx.db.add_settlement(
            ctx.active_group_id,
            owner_user_id=ctx.owner_user_id,
            from_member=src,
            to_member=dst,
            amount=amt,
            note=self.note,
            settle_date=s_date,
        )
        note_part = f" ({self.note})" if self.note else ""
        msg = f"Recorded Transfer #{sid}: {src} -> {dst} = {format_money(amt, currency)}{note_part} on {s_date}."
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
            "type": "TransferOp",
            "from": self.from_member,
            "to": self.to_member,
            "amount": self.amount_expr.pretty(),
            "note": self.note,
            "date": self.settle_date,
            "result": self.result,
        }

    def pretty_ast(self, indent: int = 0) -> str:
        return (
            f"{'  ' * indent}TransferOp({self.from_member!r} -> {self.to_member!r}, "
            f"amount={self.amount_expr.pretty()}, note={self.note!r})"
        )


@dataclass
class AssertBalancedOp(BaseOp):
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        balances = compute_balances(ctx.db, ctx.active_group_id, owner_user_id=ctx.owner_user_id)
        net_sum = sum((b["net"] for b in balances), Decimal("0"))
        if net_sum != 0:
            raise SemanticError(f"Assertion failed: ledger imbalance detected (sum = {net_sum}).")
        self.result = {
            "balanced": True,
            "net_sum": str(net_sum),
            "message": f"Assertion passed: ledger balanced (Σ net_balance == 0 across {len(balances)} members).",
        }
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {"type": "AssertBalancedOp", "result": self.result}

    def pretty_ast(self, indent: int = 0) -> str:
        return f"{'  ' * indent}AssertBalancedOp()"


@dataclass
class QueryOp(BaseOp):
    query_kind: str  # summary, balances, person_balance, expenses, members, groups, env, settle
    target_member: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        grp = ctx.group
        currency = grp["currency"]

        if self.query_kind == "env":
            lines = ["Symbol Table (Environment):"]
            if not ctx.env and not ctx.rules:
                lines.append("  (empty — use 'let x = ...' or 'rule r = ...')")
            for k, tv in ctx.env.items():
                lines.append(f"  let {k}: {tv.kind.value} = {tv.format_display(currency)}")
            for k, r in ctx.rules.items():
                lines.append(f"  rule {k} = {r.pretty()}")
            self.result = {
                "variables": {k: {"type": v.kind.value, "value": v.format_display(currency)} for k, v in ctx.env.items()},
                "rules": {k: r.pretty() for k, r in ctx.rules.items()},
                "message": "\n".join(lines),
            }

        elif self.query_kind == "members":
            members = ctx.db.list_members(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            msg = (
                f"Members in '{grp['name']}' ({len(members)}): [{', '.join(members)}]"
                if members
                else f"No members in '{grp['name']}' yet."
            )
            self.result = {"members": members, "message": msg}

        elif self.query_kind == "groups":
            groups = ctx.db.list_groups(owner_user_id=ctx.owner_user_id)
            lines = ["Workspaces:"]
            for g in groups:
                marker = " *active*" if g["id"] == ctx.active_group_id else ""
                lines.append(
                    f"  - {g['name']} ({g['currency']}, {g['member_count']} members, {g['expense_count']} expenses){marker}"
                )
            self.result = {"groups": groups, "message": "\n".join(lines)}

        elif self.query_kind == "expenses":
            expenses = ctx.db.list_expenses(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
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
            balances = compute_balances(ctx.db, ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            if not balances:
                msg = f"No members in '{grp['name']}' yet."
            else:
                lines = [f"Balances in '{grp['name']}':"]
                for b in balances:
                    net_val = b["net"]
                    status = (
                        f"+{format_money(net_val, currency)} (creditor)"
                        if net_val > 0
                        else f"{format_money(net_val, currency)} (debtor)"
                        if net_val < 0
                        else f"{format_money(Decimal('0'), currency)} (settled)"
                    )
                    lines.append(
                        f"  - {b['member']}: Paid {format_money(b['paid'], currency)} | "
                        f"Share {format_money(b['owed'], currency)} | Net {status}"
                    )
                msg = "\n".join(lines)
            self.result = {
                "balances": [
                    {"member": b["member"], "paid": str(b["paid"]), "owed": str(b["owed"]), "net": str(b["net"])}
                    for b in balances
                ],
                "message": msg,
            }

        elif self.query_kind == "settle":
            balances = compute_balances(ctx.db, ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            transfers = compute_optimal_settlements(balances, currency)
            if not transfers:
                msg = f"All settled up in '{grp['name']}'! Zero transfers needed."
            else:
                lines = [f"Optimal Settlement Plan for '{grp['name']}' ({len(transfers)} transfer(s)):"]
                for i, tr in enumerate(transfers, 1):
                    lines.append(f"  {i}. {tr['from']} -> {tr['to']} = {tr['formatted']}")
                msg = "\n".join(lines)
            self.result = {
                "transfers": [{**t, "amount": str(t["amount"])} for t in transfers],
                "message": msg,
            }

        elif self.query_kind == "summary":
            members = ctx.db.list_members(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            expenses = ctx.db.list_expenses(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            settlements = ctx.db.list_settlements(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            balances = compute_balances(ctx.db, ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            transfers = compute_optimal_settlements(balances, currency)
            total_spent = sum((e["total"] for e in expenses), Decimal("0"))
            avg_per_member = (total_spent / len(members)) if members else Decimal("0")
            top_payer = max(balances, key=lambda b: b["paid"]) if balances else None
            lines = [
                f"Summary for '{grp['name']}' ({currency}):",
                f"  Members        : {len(members)} ([{', '.join(members)}])",
                f"  Expenses/Bills : {len(expenses)}",
                f"  Transfers Paid : {len(settlements)}",
                f"  Total Spent    : {format_money(total_spent, currency)}",
                f"  Avg per Member : {format_money(avg_per_member, currency)}",
            ]
            if top_payer and top_payer["paid"] > 0:
                lines.append(f"  Top Payer      : {top_payer['member']} ({format_money(top_payer['paid'], currency)})")
            lines.append(f"  Transfers Left : {len(transfers)}")
            self.result = {
                "total_spent": str(total_spent),
                "average_per_member": str(avg_per_member),
                "expense_count": len(expenses),
                "member_count": len(members),
                "transfers_remaining": len(transfers),
                "message": "\n".join(lines),
            }

        elif self.query_kind == "person_balance":
            assert self.target_member is not None
            canonical = resolve_member_strict(
                ctx.db, ctx.active_group_id, self.target_member, owner_user_id=ctx.owner_user_id
            )
            balances = compute_balances(ctx.db, ctx.active_group_id, owner_user_id=ctx.owner_user_id)
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
                lines.append(f"  Status: Owes {format_money(-net, currency)}")
                for t in outgoing:
                    lines.append(f"    -> Pay {t['to']} {t['formatted']}")
            elif net > 0:
                lines.append(f"  Status: Owed {format_money(net, currency)}")
                for t in incoming:
                    lines.append(f"    <- Receive {t['formatted']} from {t['from']}")
            else:
                lines.append("  Status: Settled")
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


@dataclass
class ControlOp(BaseOp):
    command: str
    result: dict[str, Any] = field(default_factory=dict)

    def action(self, ctx: ExecutionContext) -> dict[str, Any]:
        if self.command == "undo":
            undone = ctx.db.undo_last_action(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            msg = f"Undid last action: {undone}" if undone else "Nothing to undo in this workspace."
            self.result = {"undone": undone, "message": msg}
        elif self.command == "reset":
            grp_name = ctx.group["name"]
            ctx.db.reset_group(ctx.active_group_id, owner_user_id=ctx.owner_user_id)
            ctx.env.clear()
            ctx.rules.clear()
            self.result = {
                "message": f"Reset workspace '{grp_name}' (cleared members, expenses, transfers, and symbol table)."
            }
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
        return f"{'  ' * indent}ControlOp(command={self.command!r})"
