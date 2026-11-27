"""Unit tests for Stage 4 (Visitor & Typed AST Generation) of SplitLang v2.0."""

from decimal import Decimal
import pytest

from controller.Response import SplitLangInterpreter
from module.ASTutils import (
    AssertBalancedOp,
    BillOp,
    BinaryOp,
    ExpenseOp,
    LetOp,
    MemberOp,
    MoneyLit,
    RuleOp,
    ScalarLit,
    TransferOp,
    WorkspaceOp,
)


@pytest.fixture
def interp():
    engine = SplitLangInterpreter(db_path=":memory:")
    yield engine
    engine.close()


def _parse_ops(interp: SplitLangInterpreter, code: str):
    analysis = interp.analyze(code)
    assert analysis["errors"] == []
    return interp.visitor.visit(analysis["tree"])


def test_workspace_and_recursive_member_list_ast(interp: SplitLangInterpreter):
    ops = _parse_ops(
        interp,
        'workspace "Trip" {\n  currency: USD\n  members: [alice, bob, charlie, dave]\n}',
    )
    assert len(ops) == 1
    assert isinstance(ops[0], WorkspaceOp)
    assert ops[0].name == "Trip"
    assert ops[0].currency == "USD"
    assert ops[0].members == ["alice", "bob", "charlie", "dave"]

    ops2 = _parse_ops(interp, "member add [eve, frank]")
    assert isinstance(ops2[0], MemberOp)
    assert ops2[0].verb == "add"
    assert ops2[0].members == ["eve", "frank"]


def test_arithmetic_precedence_ast_structure(interp: SplitLangInterpreter):
    # 120k + 30k * 2 -> BinOp('+', Money(120000), BinOp('*', Money(30000), Scalar(2)))
    ops = _parse_ops(interp, "let total = 120k + 30k * 2")
    assert isinstance(ops[0], LetOp)
    ast = ops[0].expr
    assert isinstance(ast, BinaryOp) and ast.op == "+"
    assert isinstance(ast.left, MoneyLit) and ast.left.value == Decimal("120000")
    assert isinstance(ast.right, BinaryOp) and ast.right.op == "*"
    assert ast.eval(interp.ctx).value == Decimal("180000")

    # Parentheses override precedence: (120k + 30k) * 2 == 300,000
    ops2 = _parse_ops(interp, "let total2 = (120k + 30k) * 2")
    assert ops2[0].expr.eval(interp.ctx).value == Decimal("300000")


def test_rule_expense_bill_transfer_assert_ast(interp: SplitLangInterpreter):
    code = """
    rule weighted = ratio { alice: 2, bob: 1 }
    expense "Hotpot" {
        payer: alice
        amount: 400k
        split: weighted
        tax: 10%
        date: 2026-11-26
    }
    bill "BBQ" {
        payer: bob
        item "Beef" = 480k for all
        item "Tea"  = 60k  for [charlie]
        discount: 60k
    }
    transfer bob -> alice = 100k note "part 1"
    assert balanced
    """
    ops = _parse_ops(interp, code)
    assert isinstance(ops[0], RuleOp) and ops[0].name == "weighted"
    assert isinstance(ops[1], ExpenseOp) and ops[1].split_node.rule_name == "weighted"
    assert isinstance(ops[2], BillOp) and len(ops[2].items) == 2
    assert isinstance(ops[3], TransferOp) and ops[3].note == "part 1"
    assert isinstance(ops[4], AssertBalancedOp)
