"""
Controller / Interpreter Pipeline for SplitLang.

Connects UI/CLI input to the 5-stage PPL pipeline:
  1. Input       -> raw DSL text
  2. Lexer       -> SplitLangLexer (ANTLR 4.9.2)
  3. Parser      -> SplitLangParser + SplitLangErrorListener
  4. Visitor/AST -> SplitLangASTGenerator -> AST Op nodes
  5. Action      -> op.action(ExecutionContext) -> Domain Logic + SQLite DB
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.tree.Tree import TerminalNodeImpl

_COMPILED_DIR = str(Path(__file__).resolve().parent.parent / "parserAnalyzer" / "CompiledFiles")
if _COMPILED_DIR not in sys.path:
    sys.path.insert(0, _COMPILED_DIR)

from SplitLangLexer import SplitLangLexer
from SplitLangParser import SplitLangParser

from module.ASTGeneration import SplitLangASTGenerator
from module.ASTutils import BaseOp, ExecutionContext
from module.Database import Database
from module.utilFunction import (
    SemanticError,
    compute_balances,
    compute_optimal_settlements,
    format_money,
)


class SplitLangErrorListener(ErrorListener):
    """Captures lexical and syntax errors cleanly without polluting stderr."""

    def __init__(self, phase: str) -> None:
        super().__init__()
        self.phase = phase
        self.errors: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e) -> None:
        self.errors.append(f"[{self.phase} Error at line {line}, col {column}] {msg}")


def format_parse_tree(tree, rule_names: list[str], symbolic_names: list[str], prefix: str = "", is_last: bool = True, is_root: bool = True) -> str:
    """Render an ANTLR4 parse tree as a readable Unicode box-drawing tree."""
    connector = "" if is_root else ("`- " if is_last else "|- ")
    if isinstance(tree, TerminalNodeImpl):
        tok = tree.getSymbol()
        t_type = tok.type
        if t_type == -1:
            return f"{prefix}{connector}EOF"
        name = symbolic_names[t_type] if 0 <= t_type < len(symbolic_names) and symbolic_names[t_type] else f"T_{t_type}"
        lexeme = tok.text.replace("\n", "\\n").replace("\r", "\\r")
        return f"{prefix}{connector}{name} {lexeme!r}"

    rule_name = rule_names[tree.getRuleIndex()]
    lines = [f"{prefix}{connector}{rule_name}"]
    child_prefix = "" if is_root else (prefix + ("   " if is_last else "|  "))
    child_count = tree.getChildCount()
    for idx in range(child_count):
        child = tree.getChild(idx)
        lines.append(
            format_parse_tree(
                child,
                rule_names,
                symbolic_names,
                prefix=child_prefix,
                is_last=(idx == child_count - 1),
                is_root=False,
            )
        )
    return "\n".join(lines)


class SplitLangInterpreter:
    """Stateful, owner-scoped interpreter session for SplitLang."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        db: Database | None = None,
        owner_user_id: int | None = None,
        active_group_id: int | None = None,
    ) -> None:
        self._owns_db = db is None
        self.db = db if db is not None else Database(db_path=db_path)
        uid = owner_user_id if owner_user_id is not None else self.db.ensure_local_cli_user()
        if active_group_id is not None:
            grp = self.db.get_group_by_id(active_group_id, owner_user_id=uid)
        else:
            grp = self.db.ensure_group("Default", currency="VND", owner_user_id=uid)
        self.ctx = ExecutionContext(db=self.db, owner_user_id=uid, active_group_id=grp["id"])
        self.visitor = SplitLangASTGenerator()

    def close(self) -> None:
        if self._owns_db:
            self.db.close()

    def analyze(self, source: str) -> dict[str, Any]:
        """Run Stage 2 (Lexer) and Stage 3 (Parser) and return diagnostics."""
        input_stream = InputStream(source)
        lexer = SplitLangLexer(input_stream)
        lex_errors = SplitLangErrorListener("Lexer")
        lexer.removeErrorListeners()
        lexer.addErrorListener(lex_errors)

        token_stream = CommonTokenStream(lexer)
        token_stream.fill()

        tokens_info: list[dict[str, Any]] = []
        symbolic = SplitLangLexer.symbolicNames
        for tok in token_stream.tokens:
            if tok.type == -1:  # EOF
                continue
            t_name = symbolic[tok.type] if 0 <= tok.type < len(symbolic) and symbolic[tok.type] else str(tok.type)
            tokens_info.append(
                {
                    "type": t_name,
                    "text": tok.text,
                    "line": tok.line,
                    "column": tok.column,
                }
            )

        parser = SplitLangParser(token_stream)
        parse_errors = SplitLangErrorListener("Syntax")
        parser.removeErrorListeners()
        parser.addErrorListener(parse_errors)

        tree = parser.program()
        all_errors = lex_errors.errors + parse_errors.errors
        parse_tree_str = format_parse_tree(tree, SplitLangParser.ruleNames, symbolic)

        return {
            "tokens": tokens_info,
            "tree": tree,
            "parse_tree": parse_tree_str,
            "errors": all_errors,
        }

    def execute(self, source: str) -> dict[str, Any]:
        """Execute one or more SplitLang statements through all 5 PPL stages."""
        stripped = source.strip()
        if not stripped:
            return {
                "ok": True,
                "stage_failed": None,
                "messages": [],
                "ops": [],
                "tokens": [],
                "parse_tree": "",
                "ast_tree": "",
                "errors": [],
            }

        # Stages 2 & 3: Lexer & Parser
        analysis = self.analyze(source)
        if analysis["errors"]:
            fallback = (
                "Syntax rejected by SplitLang grammar — nothing was executed.\n"
                + "\n".join(f"  * {err}" for err in analysis["errors"])
                + "\nTip: Type 'help' to see valid SplitLang syntax."
            )
            return {
                "ok": False,
                "stage_failed": "lexer_parser",
                "messages": [fallback],
                "ops": [],
                "tokens": analysis["tokens"],
                "parse_tree": analysis["parse_tree"],
                "ast_tree": "(AST not built due to syntax error)",
                "errors": analysis["errors"],
            }

        # Stage 4: Visitor -> AST Op generation
        try:
            ops: list[BaseOp] = self.visitor.visit(analysis["tree"]) or []
        except SemanticError as exc:
            err_msg = f"[Semantic Error] {exc}"
            return {
                "ok": False,
                "stage_failed": "semantic",
                "messages": [err_msg],
                "ops": [],
                "tokens": analysis["tokens"],
                "parse_tree": analysis["parse_tree"],
                "ast_tree": "(AST evaluation halted by semantic error)",
                "errors": [err_msg],
            }

        ast_tree_str = (
            "Program(\n"
            + "\n".join(op.pretty_ast(indent=1) for op in ops)
            + "\n)"
            if ops
            else "Program()"
        )

        # Stage 5: Action execution (Domain Logic + SQLite DB)
        messages: list[str] = []
        op_dicts: list[dict[str, Any]] = []
        errors: list[str] = []

        for op in ops:
            try:
                res = op.action(self.ctx)
                op_dicts.append(res)
                msg = res.get("result", {}).get("message", "")
                if msg:
                    messages.append(msg)
            except SemanticError as exc:
                err_msg = f"[Semantic Error] {exc}"
                errors.append(err_msg)
                messages.append(err_msg)
                return {
                    "ok": False,
                    "stage_failed": "semantic",
                    "messages": messages,
                    "ops": op_dicts,
                    "tokens": analysis["tokens"],
                    "parse_tree": analysis["parse_tree"],
                    "ast_tree": ast_tree_str,
                    "errors": errors,
                }

        return {
            "ok": True,
            "stage_failed": None,
            "messages": messages,
            "ops": op_dicts,
            "tokens": analysis["tokens"],
            "parse_tree": analysis["parse_tree"],
            "ast_tree": ast_tree_str,
            "errors": [],
        }

    def get_dashboard_state(self) -> dict[str, Any]:
        """Return live trimmed, JSON-serializable state for the active user's group."""
        from decimal import Decimal

        uid = self.ctx.owner_user_id
        grp = self.ctx.group
        currency = grp["currency"]
        members = self.db.list_members(grp["id"], owner_user_id=uid)
        expenses = self.db.list_expenses(grp["id"], owner_user_id=uid)
        balances = compute_balances(self.db, grp["id"], owner_user_id=uid)
        transfers = compute_optimal_settlements(balances, currency)
        groups = self.db.list_groups(owner_user_id=uid)

        total_spent_dec = sum((e["total"] for e in expenses), Decimal("0"))

        # Control #17 (Trim API responses): expose only needed public fields (never owner_user_id)
        return {
            "group": {"id": grp["id"], "name": grp["name"], "currency": grp["currency"]},
            "groups": [
                {
                    "id": g["id"],
                    "name": g["name"],
                    "currency": g["currency"],
                    "member_count": g["member_count"],
                    "expense_count": g["expense_count"],
                }
                for g in groups
            ],
            "currency": currency,
            "members": members,
            "total_spent": format_money(total_spent_dec, currency),
            "total_spent_raw": str(total_spent_dec),
            "expense_count": len(expenses),
            "balances": [
                {
                    "member": b["member"],
                    "paid": format_money(b["paid"], currency),
                    "paid_raw": float(b["paid"]),
                    "owed": format_money(b["owed"], currency),
                    "owed_raw": float(b["owed"]),
                    "net_raw": float(b["net"]),
                    "net": (
                        f"+{format_money(b['net'], currency)}"
                        if b["net"] > 0
                        else format_money(b["net"], currency)
                    ),
                }
                for b in balances
            ],
            "transfers": [
                {
                    "from": tr["from"],
                    "to": tr["to"],
                    "amount": str(tr["amount"]),
                    "formatted": tr["formatted"],
                }
                for tr in transfers
            ],
            "expenses": [
                {
                    "id": e["id"],
                    "kind": e["kind"],
                    "date": e["expense_date"],
                    "payer": e["payer"],
                    "description": e["description"],
                    "mode": "ITEMIZED" if e["kind"] == "bill" else e["split_mode"].upper(),
                    "subtotal": format_money(e["subtotal"], currency),
                    "discount": format_money(e["discount"], currency) if e["discount"] > 0 else None,
                    "tax": format_money(e["tax_amount"], currency) if e["tax_amount"] > 0 else None,
                    "tip": format_money(e["tip_amount"], currency) if e["tip_amount"] > 0 else None,
                    "total": format_money(e["total"], currency),
                    "items": e["items"],
                    "shares": [
                        {"member": m, "formatted": format_money(s, currency)}
                        for m, s in e["shares"].items()
                    ],
                    "shares_text": ", ".join(
                        f"{m}: {format_money(s, currency)}" for m, s in e["shares"].items()
                    ),
                }
                for e in reversed(expenses)
            ],
        }
