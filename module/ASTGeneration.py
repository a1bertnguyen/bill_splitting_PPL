"""
ANTLR4 Parse Tree -> Abstract Syntax Tree (AST) Visitor for SplitLang.

Subclasses the ANTLR-generated SplitLangVisitor to transform concrete parse trees
into clean, execution-ready AST Op objects while stripping syntactic sugar.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure ANTLR-generated CompiledFiles is importable
_COMPILED_DIR = str(Path(__file__).resolve().parent.parent / "parserAnalyzer" / "CompiledFiles")
if _COMPILED_DIR not in sys.path:
    sys.path.insert(0, _COMPILED_DIR)

from SplitLangParser import SplitLangParser
from SplitLangVisitor import SplitLangVisitor

from module.ASTutils import (
    BaseOp,
    BillOp,
    ControlOp,
    CurrencyOp,
    ExpenseOp,
    GroupOp,
    MemberOp,
    QueryOp,
    SettleOp,
    SettleUpOp,
)
from module.utilFunction import SemanticError


class SplitLangASTGenerator(SplitLangVisitor):
    """
    Walks an ANTLR4 parse tree for SplitLang and builds a list of AST Op nodes.

    Demonstrates all four PPL Visitor patterns:
      1. Leaf rules returning primitive values (visitAmountAtom, visitPerson, visitDescription)
      2. Recursive rules gathering lists (visitPersonList, visitExactAllocList, ...)
      3. Expression evaluation respecting operator precedence (visitMulDivExpr, visitAddSubExpr)
      4. Request rules building high-level AST Op nodes (visitExpenseStmt, visitBillStmt, ...)
    """

    # ------------------------------------------------------------------
    # Top-level Program & Statement Dispatch
    # ------------------------------------------------------------------

    def visitProgram(self, ctx: SplitLangParser.ProgramContext) -> list[BaseOp]:
        ops: list[BaseOp] = []
        for stmt_ctx in ctx.statement():
            op = self.visit(stmt_ctx)
            if op is not None:
                ops.append(op)
        return ops

    def visitStatement(self, ctx: SplitLangParser.StatementContext) -> BaseOp:
        # Delegate directly to the single matched statement child
        return self.visit(ctx.getChild(0))

    # ------------------------------------------------------------------
    # 1. Group, Currency & Member Rules
    # ------------------------------------------------------------------

    def visitGroupStmt(self, ctx: SplitLangParser.GroupStmtContext) -> GroupOp:
        name = self.visit(ctx.description())
        return GroupOp(name=name)

    def visitCurrencyStmt(self, ctx: SplitLangParser.CurrencyStmtContext) -> CurrencyOp:
        code = ctx.CURRENCY_CODE().getText().upper()
        return CurrencyOp(currency=code)

    def visitAddMembersStmt(self, ctx: SplitLangParser.AddMembersStmtContext) -> MemberOp:
        members = self.visit(ctx.personList())
        return MemberOp(verb="add", members=members)

    def visitRemoveMembersStmt(self, ctx: SplitLangParser.RemoveMembersStmtContext) -> MemberOp:
        members = self.visit(ctx.personList())
        return MemberOp(verb="remove", members=members)

    # ------------------------------------------------------------------
    # 2. Expense Rule & Split Clauses
    # ------------------------------------------------------------------

    def visitExpenseStmt(self, ctx: SplitLangParser.ExpenseStmtContext) -> ExpenseOp:
        payer = self.visit(ctx.person())
        amount = self.visit(ctx.expr())
        description = self.visit(ctx.description()) if ctx.description() else "Expense"
        split_spec = (
            self.visit(ctx.splitClause())
            if ctx.splitClause()
            else {"mode": "equal", "among": None, "excluding": None}
        )
        modifiers = [self.visit(m) for m in ctx.modifier()]
        exp_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None

        return ExpenseOp(
            payer=payer,
            amount=amount,
            description=description,
            split_spec=split_spec,
            modifiers=modifiers,
            expense_date=exp_date,
        )

    def visitEqualSplit(self, ctx: SplitLangParser.EqualSplitContext) -> dict[str, Any]:
        if ctx.AMONG():
            return {"mode": "equal", "among": self.visit(ctx.personList()), "excluding": None}
        if ctx.EXCLUDING():
            return {"mode": "equal", "among": None, "excluding": self.visit(ctx.personList())}
        return {"mode": "equal", "among": None, "excluding": None}

    def visitShorthandEqualSplit(
        self, ctx: SplitLangParser.ShorthandEqualSplitContext
    ) -> dict[str, Any]:
        if ctx.AMONG():
            return {"mode": "equal", "among": self.visit(ctx.personList()), "excluding": None}
        return {"mode": "equal", "among": None, "excluding": self.visit(ctx.personList())}

    def visitExactSplit(self, ctx: SplitLangParser.ExactSplitContext) -> dict[str, Any]:
        allocs = self.visit(ctx.exactAllocList())
        return {"mode": "exact", "allocations": allocs}

    def visitPercentSplit(self, ctx: SplitLangParser.PercentSplitContext) -> dict[str, Any]:
        allocs = self.visit(ctx.percentAllocList())
        return {"mode": "percent", "allocations": allocs}

    def visitRatioSplit(self, ctx: SplitLangParser.RatioSplitContext) -> dict[str, Any]:
        allocs = self.visit(ctx.ratioAllocList())
        return {"mode": "ratio", "allocations": allocs}

    # ------------------------------------------------------------------
    # Modifiers & Date
    # ------------------------------------------------------------------

    def _parse_modifier(self, kind: str, ctx: Any) -> dict[str, Any]:
        if ctx.PERCENT_LIT():
            raw = ctx.PERCENT_LIT().getText().rstrip("%")
            return {"kind": kind, "is_percent": True, "value": Decimal(raw)}
        val = self.visit(ctx.expr())
        return {"kind": kind, "is_percent": False, "value": val}

    def visitTaxMod(self, ctx: SplitLangParser.TaxModContext) -> dict[str, Any]:
        return self._parse_modifier("tax", ctx)

    def visitTipMod(self, ctx: SplitLangParser.TipModContext) -> dict[str, Any]:
        return self._parse_modifier("tip", ctx)

    def visitDiscountMod(self, ctx: SplitLangParser.DiscountModContext) -> dict[str, Any]:
        return self._parse_modifier("discount", ctx)

    def visitDateClause(self, ctx: SplitLangParser.DateClauseContext) -> str:
        return ctx.DATE().getText().replace("/", "-")

    # ------------------------------------------------------------------
    # 3. Itemized Bill Block
    # ------------------------------------------------------------------

    def visitBillStmt(self, ctx: SplitLangParser.BillStmtContext) -> BillOp:
        title = self.visit(ctx.description())
        payer = self.visit(ctx.person())
        b_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None

        items: list[dict[str, Any]] = []
        modifiers: list[dict[str, Any]] = []
        for entry_ctx in ctx.billEntry():
            entry = self.visit(entry_ctx)
            if entry["entry_type"] == "item":
                items.append(entry)
            else:
                modifiers.append(entry["modifier"])

        return BillOp(
            title=title,
            payer=payer,
            items=items,
            modifiers=modifiers,
            bill_date=b_date,
        )

    def visitBillItemEntry(self, ctx: SplitLangParser.BillItemEntryContext) -> dict[str, Any]:
        name = self.visit(ctx.description())
        amount = self.visit(ctx.expr())
        if ctx.ALL():
            excluding = self.visit(ctx.personList()) if ctx.EXCLUDING() else []
            return {
                "entry_type": "item",
                "name": name,
                "amount": amount,
                "for_all": True,
                "excluding": excluding,
                "consumers": [],
            }
        consumers = self.visit(ctx.personList())
        return {
            "entry_type": "item",
            "name": name,
            "amount": amount,
            "for_all": False,
            "excluding": [],
            "consumers": consumers,
        }

    def visitBillTaxEntry(self, ctx: SplitLangParser.BillTaxEntryContext) -> dict[str, Any]:
        return {"entry_type": "modifier", "modifier": self._parse_modifier("tax", ctx)}

    def visitBillTipEntry(self, ctx: SplitLangParser.BillTipEntryContext) -> dict[str, Any]:
        return {"entry_type": "modifier", "modifier": self._parse_modifier("tip", ctx)}

    def visitBillDiscountEntry(
        self, ctx: SplitLangParser.BillDiscountEntryContext
    ) -> dict[str, Any]:
        return {"entry_type": "modifier", "modifier": self._parse_modifier("discount", ctx)}

    # ------------------------------------------------------------------
    # 4. Settlement Rules
    # ------------------------------------------------------------------

    def visitDirectPaySettle(self, ctx: SplitLangParser.DirectPaySettleContext) -> SettleOp:
        src = self.visit(ctx.person(0))
        dst = self.visit(ctx.person(1))
        amount = self.visit(ctx.expr())
        note = self.visit(ctx.description()) if ctx.description() else ""
        s_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None
        return SettleOp(from_member=src, to_member=dst, amount=amount, note=note, settle_date=s_date)

    def visitKeywordSettle(self, ctx: SplitLangParser.KeywordSettleContext) -> SettleOp:
        src = self.visit(ctx.person(0))
        dst = self.visit(ctx.person(1))
        amount = self.visit(ctx.expr())
        note = self.visit(ctx.description()) if ctx.description() else ""
        s_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None
        return SettleOp(from_member=src, to_member=dst, amount=amount, note=note, settle_date=s_date)

    def visitSettleUpStmt(self, ctx: SplitLangParser.SettleUpStmtContext) -> SettleUpOp:
        return SettleUpOp()

    # ------------------------------------------------------------------
    # 5. Query & Control Rules
    # ------------------------------------------------------------------

    def visitShowQuery(self, ctx: SplitLangParser.ShowQueryContext) -> QueryOp:
        target = self.visit(ctx.queryTarget())
        return QueryOp(query_kind=target)

    def visitQueryTarget(self, ctx: SplitLangParser.QueryTargetContext) -> str:
        if ctx.MEMBER_KW():
            return "members"
        if ctx.EXPENSES():
            return "expenses"
        if ctx.BALANCES():
            return "balances"
        if ctx.SUMMARY():
            return "summary"
        if ctx.SETTLEMENTS():
            return "settlements"
        if ctx.GROUPS():
            return "groups"
        return "summary"

    def visitWhoOwesWhomQuery(self, ctx: SplitLangParser.WhoOwesWhomQueryContext) -> QueryOp:
        return QueryOp(query_kind="who_owes_whom")

    def visitHowMuchOwesQuery(self, ctx: SplitLangParser.HowMuchOwesQueryContext) -> QueryOp:
        member = self.visit(ctx.person())
        return QueryOp(query_kind="how_much_owes", target_member=member)

    def visitPersonBalanceQuery(self, ctx: SplitLangParser.PersonBalanceQueryContext) -> QueryOp:
        member = self.visit(ctx.person())
        return QueryOp(query_kind="person_balance", target_member=member)

    def visitUndoCtrl(self, ctx: SplitLangParser.UndoCtrlContext) -> ControlOp:
        return ControlOp(command="undo")

    def visitResetCtrl(self, ctx: SplitLangParser.ResetCtrlContext) -> ControlOp:
        return ControlOp(command="reset")

    def visitClearCtrl(self, ctx: SplitLangParser.ClearCtrlContext) -> ControlOp:
        return ControlOp(command="clear")

    def visitHelpCtrl(self, ctx: SplitLangParser.HelpCtrlContext) -> ControlOp:
        return ControlOp(command="help")

    # ------------------------------------------------------------------
    # 6. Recursive List Rules (Right-Recursion in Grammar)
    # ------------------------------------------------------------------

    def visitPersonList(self, ctx: SplitLangParser.PersonListContext) -> list[str]:
        out = [self.visit(ctx.person())]
        if ctx.personList():
            out += self.visit(ctx.personList())
        return out

    def visitExactAllocList(
        self, ctx: SplitLangParser.ExactAllocListContext
    ) -> list[tuple[str, Decimal]]:
        out = [self.visit(ctx.exactAlloc())]
        if ctx.exactAllocList():
            out += self.visit(ctx.exactAllocList())
        return out

    def visitExactAlloc(self, ctx: SplitLangParser.ExactAllocContext) -> tuple[str, Decimal]:
        return (self.visit(ctx.person()), self.visit(ctx.expr()))

    def visitPercentAllocList(
        self, ctx: SplitLangParser.PercentAllocListContext
    ) -> list[tuple[str, Decimal]]:
        out = [self.visit(ctx.percentAlloc())]
        if ctx.percentAllocList():
            out += self.visit(ctx.percentAllocList())
        return out

    def visitPercentAlloc(self, ctx: SplitLangParser.PercentAllocContext) -> tuple[str, Decimal]:
        pct = Decimal(ctx.PERCENT_LIT().getText().rstrip("%"))
        return (self.visit(ctx.person()), pct)

    def visitRatioAllocList(
        self, ctx: SplitLangParser.RatioAllocListContext
    ) -> list[tuple[str, Decimal]]:
        out = [self.visit(ctx.ratioAlloc())]
        if ctx.ratioAllocList():
            out += self.visit(ctx.ratioAllocList())
        return out

    def visitRatioAlloc(self, ctx: SplitLangParser.RatioAllocContext) -> tuple[str, Decimal]:
        return (self.visit(ctx.person()), Decimal(ctx.NUMBER().getText()))

    # ------------------------------------------------------------------
    # 7. Arithmetic Expressions (Precedence: * / > + -, Parentheses)
    # ------------------------------------------------------------------

    def visitMulDivExpr(self, ctx: SplitLangParser.MulDivExprContext) -> Decimal:
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        if ctx.op.type == SplitLangParser.STAR:
            return left * right
        if right == 0:
            raise SemanticError("Division by zero in amount expression.")
        return left / right

    def visitAddSubExpr(self, ctx: SplitLangParser.AddSubExprContext) -> Decimal:
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        if ctx.op.type == SplitLangParser.PLUS:
            return left + right
        return left - right

    def visitParenExpr(self, ctx: SplitLangParser.ParenExprContext) -> Decimal:
        return self.visit(ctx.expr())

    def visitAtomExpr(self, ctx: SplitLangParser.AtomExprContext) -> Decimal:
        return self.visit(ctx.amountAtom())

    def visitAmountAtom(self, ctx: SplitLangParser.AmountAtomContext) -> Decimal:
        if ctx.MONEY_K():
            return Decimal(ctx.MONEY_K().getText()[:-1]) * Decimal("1000")
        if ctx.MONEY_M():
            return Decimal(ctx.MONEY_M().getText()[:-1]) * Decimal("1000000")
        if ctx.MONEY_USD():
            return Decimal(ctx.MONEY_USD().getText()[1:])
        return Decimal(ctx.NUMBER().getText())

    # ------------------------------------------------------------------
    # 8. Leaf Helpers (Person & Description)
    # ------------------------------------------------------------------

    def visitPerson(self, ctx: SplitLangParser.PersonContext) -> str:
        raw = ctx.ID().getText()
        # Allow natural English possessive like "alice's" in "what is alice's balance?"
        if raw.lower().endswith("'s") and len(raw) > 2:
            raw = raw[:-2]
        return raw

    def visitDescription(self, ctx: SplitLangParser.DescriptionContext) -> str:
        if ctx.STRING():
            raw = ctx.STRING().getText()
            # Strip enclosing quotes and unescape simple escaped quotes
            inner = raw[1:-1]
            return inner.replace(r'\"', '"').replace(r"\'", "'")
        return " ".join(tok.getText() for tok in ctx.ID())
