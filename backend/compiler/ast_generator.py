"""
ANTLR4 Parse Tree -> Abstract Syntax Tree (AST) Visitor for SplitLang v2.0.

Builds pure, typed AST nodes (ExprNode, SplitNode, Command Ops) without executing
side effects during tree traversal (strict separation of Syntax -> AST -> Evaluation).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

_COMPILED_DIR = str(Path(__file__).resolve().parent / "antlr" / "CompiledFiles")
if _COMPILED_DIR not in sys.path:
    sys.path.insert(0, _COMPILED_DIR)

from SplitLangParser import SplitLangParser
from SplitLangVisitor import SplitLangVisitor

from backend.compiler.ast_nodes import (
    AllMembersLit,
    AssertBalancedOp,
    BaseOp,
    BillItemNode,
    BillOp,
    BinaryOp,
    ControlOp,
    CurrencyOp,
    ExpenseOp,
    ExprNode,
    LetOp,
    MemberOp,
    MoneyLit,
    PercentLit,
    QueryOp,
    RuleOp,
    ScalarLit,
    SetLit,
    SplitNode,
    TransferOp,
    UnaryNeg,
    VarRef,
    WorkspaceOp,
)
from backend.services.split_math import SemanticError


def _unquote(token_text: str) -> str:
    return token_text[1:-1].replace(r'\"', '"').replace(r"\'", "'")


class SplitLangASTGenerator(SplitLangVisitor):
    """Transforms ANTLR4 SplitLang v2.0 parse trees into clean AST Op trees."""

    # ------------------------------------------------------------------
    # Program & Statement Dispatch
    # ------------------------------------------------------------------

    def visitProgram(self, ctx: SplitLangParser.ProgramContext) -> list[BaseOp]:
        ops: list[BaseOp] = []
        for stmt_ctx in ctx.statement():
            op = self.visit(stmt_ctx)
            if op is not None:
                ops.append(op)
        return ops

    def visitStatement(self, ctx: SplitLangParser.StatementContext) -> BaseOp:
        return self.visit(ctx.getChild(0))

    # ------------------------------------------------------------------
    # 1. Workspace, Currency & Members
    # ------------------------------------------------------------------

    def visitWorkspaceStmt(self, ctx: SplitLangParser.WorkspaceStmtContext) -> WorkspaceOp:
        name = _unquote(ctx.STRING().getText())
        currency: str | None = None
        members: list[str] | None = None
        for f_ctx in ctx.wsField():
            kind, val = self.visit(f_ctx)
            if kind == "currency":
                currency = val
            elif kind == "members":
                members = val
        return WorkspaceOp(name=name, currency=currency, members=members)

    def visitWsCurrencyField(self, ctx: SplitLangParser.WsCurrencyFieldContext) -> tuple[str, str]:
        return ("currency", ctx.CURRENCY_CODE().getText().upper())

    def visitWsMembersField(self, ctx: SplitLangParser.WsMembersFieldContext) -> tuple[str, list[str]]:
        ids = self.visit(ctx.idList()) if ctx.idList() else []
        return ("members", ids)

    def visitCurrencyStmt(self, ctx: SplitLangParser.CurrencyStmtContext) -> CurrencyOp:
        return CurrencyOp(currency=ctx.CURRENCY_CODE().getText().upper())

    def visitMemberAddStmt(self, ctx: SplitLangParser.MemberAddStmtContext) -> MemberOp:
        return MemberOp(verb="add", members=self.visit(ctx.idList()))

    def visitMemberRemoveStmt(self, ctx: SplitLangParser.MemberRemoveStmtContext) -> MemberOp:
        return MemberOp(verb="remove", members=self.visit(ctx.idList()))

    # ------------------------------------------------------------------
    # 2. Symbol Table Bindings & Reusable Rules
    # ------------------------------------------------------------------

    def visitLetStmt(self, ctx: SplitLangParser.LetStmtContext) -> LetOp:
        return LetOp(name=ctx.ID().getText(), expr=self.visit(ctx.expr()))

    def visitRuleStmt(self, ctx: SplitLangParser.RuleStmtContext) -> RuleOp:
        return RuleOp(name=ctx.ID().getText(), split_node=self.visit(ctx.splitExpr()))

    # ------------------------------------------------------------------
    # 3. Expenses (Inline & Block Forms)
    # ------------------------------------------------------------------

    def visitInlineExpenseStmt(self, ctx: SplitLangParser.InlineExpenseStmtContext) -> ExpenseOp:
        desc = _unquote(ctx.STRING().getText())
        payer = ctx.ID().getText()
        amt_expr = self.visit(ctx.expr())
        split_node = self.visit(ctx.splitExpr()) if ctx.splitExpr() else SplitNode(mode="equal")
        mods = [self.visit(m) for m in ctx.modifierClause()]
        exp_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None
        return ExpenseOp(
            description=desc,
            payer=payer,
            amount_expr=amt_expr,
            split_node=split_node,
            modifier_exprs=mods,
            expense_date=exp_date,
        )

    def visitBlockExpenseStmt(self, ctx: SplitLangParser.BlockExpenseStmtContext) -> ExpenseOp:
        desc = _unquote(ctx.STRING().getText())
        payer: str | None = None
        amount_expr: ExprNode | None = None
        split_node = SplitNode(mode="equal")
        mods: list[tuple[str, ExprNode]] = []
        exp_date: str | None = None

        for f_ctx in ctx.expenseField():
            kind, val = self.visit(f_ctx)
            if kind == "payer":
                payer = val
            elif kind == "amount":
                amount_expr = val
            elif kind == "split":
                split_node = val
            elif kind in ("discount", "tax", "tip"):
                mods.append((kind, val))
            elif kind == "date":
                exp_date = val

        if not payer:
            raise SemanticError(f"Expense '{desc}' block is missing required 'payer:' field.")
        if amount_expr is None:
            raise SemanticError(f"Expense '{desc}' block is missing required 'amount:' field.")

        return ExpenseOp(
            description=desc,
            payer=payer,
            amount_expr=amount_expr,
            split_node=split_node,
            modifier_exprs=mods,
            expense_date=exp_date,
        )

    def visitExpPayerField(self, ctx: SplitLangParser.ExpPayerFieldContext):
        return ("payer", ctx.ID().getText())

    def visitExpAmountField(self, ctx: SplitLangParser.ExpAmountFieldContext):
        return ("amount", self.visit(ctx.expr()))

    def visitExpSplitField(self, ctx: SplitLangParser.ExpSplitFieldContext):
        return ("split", self.visit(ctx.splitExpr()))

    def visitExpDiscountField(self, ctx: SplitLangParser.ExpDiscountFieldContext):
        return ("discount", self.visit(ctx.expr()))

    def visitExpTaxField(self, ctx: SplitLangParser.ExpTaxFieldContext):
        return ("tax", self.visit(ctx.expr()))

    def visitExpTipField(self, ctx: SplitLangParser.ExpTipFieldContext):
        return ("tip", self.visit(ctx.expr()))

    def visitExpDateField(self, ctx: SplitLangParser.ExpDateFieldContext):
        return ("date", ctx.DATE().getText())

    def visitInlineDiscountMod(self, ctx: SplitLangParser.InlineDiscountModContext):
        return ("discount", self.visit(ctx.expr()))

    def visitInlineTaxMod(self, ctx: SplitLangParser.InlineTaxModContext):
        return ("tax", self.visit(ctx.expr()))

    def visitInlineTipMod(self, ctx: SplitLangParser.InlineTipModContext):
        return ("tip", self.visit(ctx.expr()))

    def visitDateClause(self, ctx: SplitLangParser.DateClauseContext) -> str:
        return ctx.DATE().getText()

    # Split Expressions
    def visitEqualSplitExpr(self, ctx: SplitLangParser.EqualSplitExprContext) -> SplitNode:
        return SplitNode(mode="equal", target_expr=self.visit(ctx.expr()))

    def visitEqualAllSplitExpr(self, ctx: SplitLangParser.EqualAllSplitExprContext) -> SplitNode:
        return SplitNode(mode="equal", target_expr=None)

    def visitExactSplitExpr(self, ctx: SplitLangParser.ExactSplitExprContext) -> SplitNode:
        allocs = self.visit(ctx.allocList()) if ctx.allocList() else []
        return SplitNode(mode="exact", alloc_exprs=allocs)

    def visitPercentSplitExpr(self, ctx: SplitLangParser.PercentSplitExprContext) -> SplitNode:
        allocs = self.visit(ctx.allocList()) if ctx.allocList() else []
        return SplitNode(mode="percent", alloc_exprs=allocs)

    def visitRatioSplitExpr(self, ctx: SplitLangParser.RatioSplitExprContext) -> SplitNode:
        allocs = self.visit(ctx.allocList()) if ctx.allocList() else []
        return SplitNode(mode="ratio", alloc_exprs=allocs)

    def visitRuleRefSplitExpr(self, ctx: SplitLangParser.RuleRefSplitExprContext) -> SplitNode:
        return SplitNode(mode="rule_ref", rule_name=ctx.ID().getText())

    # ------------------------------------------------------------------
    # 4. Itemized Bill Block
    # ------------------------------------------------------------------

    def visitBillStmt(self, ctx: SplitLangParser.BillStmtContext) -> BillOp:
        title = _unquote(ctx.STRING().getText())
        payer: str | None = None
        b_date: str | None = None
        items: list[BillItemNode] = []
        mods: list[tuple[str, ExprNode]] = []

        for f_ctx in ctx.billField():
            kind, val = self.visit(f_ctx)
            if kind == "payer":
                payer = val
            elif kind == "date":
                b_date = val
            elif kind == "item":
                items.append(val)
            elif kind in ("discount", "tax", "tip"):
                mods.append((kind, val))

        if not payer:
            raise SemanticError(f"Bill '{title}' is missing required 'payer:' field.")
        if not items:
            raise SemanticError(f"Bill '{title}' must contain at least one 'item' entry.")

        return BillOp(title=title, payer=payer, items=items, modifier_exprs=mods, bill_date=b_date)

    def visitBillPayerField(self, ctx: SplitLangParser.BillPayerFieldContext):
        return ("payer", ctx.ID().getText())

    def visitBillDateField(self, ctx: SplitLangParser.BillDateFieldContext):
        return ("date", ctx.DATE().getText())

    def visitBillItemField(self, ctx: SplitLangParser.BillItemFieldContext):
        item = BillItemNode(
            name=_unquote(ctx.STRING().getText()),
            amount_expr=self.visit(ctx.expr(0)),
            target_expr=self.visit(ctx.expr(1)),
        )
        return ("item", item)

    def visitBillDiscountField(self, ctx: SplitLangParser.BillDiscountFieldContext):
        return ("discount", self.visit(ctx.expr()))

    def visitBillTaxField(self, ctx: SplitLangParser.BillTaxFieldContext):
        return ("tax", self.visit(ctx.expr()))

    def visitBillTipField(self, ctx: SplitLangParser.BillTipFieldContext):
        return ("tip", self.visit(ctx.expr()))

    # ------------------------------------------------------------------
    # 5. Transfers, Assertions, Queries & Controls
    # ------------------------------------------------------------------

    def visitTransferStmt(self, ctx: SplitLangParser.TransferStmtContext) -> TransferOp:
        src = ctx.ID(0).getText()
        dst = ctx.ID(1).getText()
        amt_expr = self.visit(ctx.expr())
        note = _unquote(ctx.STRING().getText()) if ctx.STRING() else ""
        s_date = self.visit(ctx.dateClause()) if ctx.dateClause() else None
        return TransferOp(from_member=src, to_member=dst, amount_expr=amt_expr, note=note, settle_date=s_date)

    def visitAssertStmt(self, ctx: SplitLangParser.AssertStmtContext) -> AssertBalancedOp:
        return AssertBalancedOp()

    def visitQuerySummary(self, ctx: SplitLangParser.QuerySummaryContext) -> QueryOp:
        return QueryOp(query_kind="summary")

    def visitQueryBalances(self, ctx: SplitLangParser.QueryBalancesContext) -> QueryOp:
        return QueryOp(query_kind="balances")

    def visitQueryPersonBalance(self, ctx: SplitLangParser.QueryPersonBalanceContext) -> QueryOp:
        return QueryOp(query_kind="person_balance", target_member=ctx.ID().getText())

    def visitQueryExpenses(self, ctx: SplitLangParser.QueryExpensesContext) -> QueryOp:
        return QueryOp(query_kind="expenses")

    def visitQueryMembers(self, ctx: SplitLangParser.QueryMembersContext) -> QueryOp:
        return QueryOp(query_kind="members")

    def visitQueryGroups(self, ctx: SplitLangParser.QueryGroupsContext) -> QueryOp:
        return QueryOp(query_kind="groups")

    def visitQueryEnv(self, ctx: SplitLangParser.QueryEnvContext) -> QueryOp:
        return QueryOp(query_kind="env")

    def visitSettleQuery(self, ctx: SplitLangParser.SettleQueryContext) -> QueryOp:
        return QueryOp(query_kind="settle")

    def visitUndoCtrl(self, ctx: SplitLangParser.UndoCtrlContext) -> ControlOp:
        return ControlOp(command="undo")

    def visitResetCtrl(self, ctx: SplitLangParser.ResetCtrlContext) -> ControlOp:
        return ControlOp(command="reset")

    def visitClearCtrl(self, ctx: SplitLangParser.ClearCtrlContext) -> ControlOp:
        return ControlOp(command="clear")

    def visitHelpCtrl(self, ctx: SplitLangParser.HelpCtrlContext) -> ControlOp:
        return ControlOp(command="help")

    # ------------------------------------------------------------------
    # 6. Recursive Lists (CFG Right-Recursion)
    # ------------------------------------------------------------------

    def visitIdList(self, ctx: SplitLangParser.IdListContext) -> list[str]:
        out = [ctx.ID().getText()]
        if ctx.idList():
            out += self.visit(ctx.idList())
        return out

    def visitAllocList(self, ctx: SplitLangParser.AllocListContext) -> list[tuple[str, ExprNode]]:
        out = [self.visit(ctx.allocEntry())]
        if ctx.allocList():
            out += self.visit(ctx.allocList())
        return out

    def visitAllocEntry(self, ctx: SplitLangParser.AllocEntryContext) -> tuple[str, ExprNode]:
        return (ctx.ID().getText(), self.visit(ctx.expr()))

    # ------------------------------------------------------------------
    # 7. Unified Typed Expressions
    # ------------------------------------------------------------------

    def visitUnaryNegExpr(self, ctx: SplitLangParser.UnaryNegExprContext) -> ExprNode:
        return UnaryNeg(self.visit(ctx.expr()))

    def visitMulDivExpr(self, ctx: SplitLangParser.MulDivExprContext) -> ExprNode:
        op = "*" if ctx.op.type == SplitLangParser.STAR else "/"
        return BinaryOp(op=op, left=self.visit(ctx.expr(0)), right=self.visit(ctx.expr(1)))

    def visitAddSubExpr(self, ctx: SplitLangParser.AddSubExprContext) -> ExprNode:
        op = "+" if ctx.op.type == SplitLangParser.PLUS else "-"
        return BinaryOp(op=op, left=self.visit(ctx.expr(0)), right=self.visit(ctx.expr(1)))

    def visitParenExpr(self, ctx: SplitLangParser.ParenExprContext) -> ExprNode:
        return self.visit(ctx.expr())

    def visitSetLitExpr(self, ctx: SplitLangParser.SetLitExprContext) -> ExprNode:
        ids = self.visit(ctx.idList()) if ctx.idList() else []
        return SetLit(tuple(ids))

    def visitAllMembersExpr(self, ctx: SplitLangParser.AllMembersExprContext) -> ExprNode:
        return AllMembersLit()

    def visitPercentLitExpr(self, ctx: SplitLangParser.PercentLitExprContext) -> ExprNode:
        return PercentLit(Decimal(ctx.PERCENT_LIT().getText().rstrip("%")))

    def visitMoneyKLitExpr(self, ctx: SplitLangParser.MoneyKLitExprContext) -> ExprNode:
        return MoneyLit(Decimal(ctx.MONEY_K().getText()[:-1]) * Decimal("1000"))

    def visitMoneyMLitExpr(self, ctx: SplitLangParser.MoneyMLitExprContext) -> ExprNode:
        return MoneyLit(Decimal(ctx.MONEY_M().getText()[:-1]) * Decimal("1000000"))

    def visitMoneyUsdLitExpr(self, ctx: SplitLangParser.MoneyUsdLitExprContext) -> ExprNode:
        return MoneyLit(Decimal(ctx.MONEY_USD().getText()[1:]))

    def visitNumberLitExpr(self, ctx: SplitLangParser.NumberLitExprContext) -> ExprNode:
        return ScalarLit(Decimal(ctx.NUMBER().getText()))

    def visitVarRefExpr(self, ctx: SplitLangParser.VarRefExprContext) -> ExprNode:
        return VarRef(ctx.ID().getText())
