"""Unit tests for Stage 4 (Visitor & Parse Tree -> AST Transformation)."""

from decimal import Decimal
import pytest

from controller.Response import SplitLangInterpreter
from module.ASTutils import BillOp, ExpenseOp, MemberOp, QueryOp, SettleOp


@pytest.fixture
def interp():
    engine = SplitLangInterpreter(db_path=":memory:")
    yield engine
    engine.close()


def _parse_ops(interp: SplitLangInterpreter, code: str):
    analysis = interp.analyze(code)
    assert analysis["errors"] == []
    return interp.visitor.visit(analysis["tree"])


def test_recursive_person_list_ast(interp: SplitLangInterpreter):
    ops = _parse_ops(interp, "add members alice, bob, charlie, dave")
    assert len(ops) == 1
    assert isinstance(ops[0], MemberOp)
    assert ops[0].verb == "add"
    assert ops[0].members == ["alice", "bob", "charlie", "dave"]


def test_arithmetic_precedence_and_parentheses(interp: SplitLangInterpreter):
    # 120k + 30k * 2 == 180,000 (not 300,000)
    ops1 = _parse_ops(interp, "alice paid 120k + 30k * 2 for dinner")
    assert isinstance(ops1[0], ExpenseOp)
    assert ops1[0].amount == Decimal("180000")

    # (120k + 30k) * 2 == 300,000
    ops2 = _parse_ops(interp, "alice paid (120k + 30k) * 2 for dinner")
    assert ops2[0].amount == Decimal("300000")

    # 1.5m - 500k / 2 == 1,250,000
    ops3 = _parse_ops(interp, "alice paid 1.5m - 500k / 2 for hotel")
    assert ops3[0].amount == Decimal("1250000")


def test_expense_modifiers_and_split_ast(interp: SplitLangInterpreter):
    code = (
        'bob paid 400k for "Hotpot Night" '
        "split ratio alice: 2, bob: 1, charlie: 1 "
        "with discount 40k with tax 10% with tip 5% on 26-11-2026"
    )
    ops = _parse_ops(interp, code)
    op = ops[0]
    assert isinstance(op, ExpenseOp)
    assert op.payer == "bob"
    assert op.description == "Hotpot Night"
    assert op.split_spec == {
        "mode": "ratio",
        "allocations": [
            ("alice", Decimal("2")),
            ("bob", Decimal("1")),
            ("charlie", Decimal("1")),
        ],
    }
    assert len(op.modifiers) == 3
    assert op.expense_date == "26-11-2026"


def test_bill_block_ast(interp: SplitLangInterpreter):
    code = """
    bill "BBQ" paid by alice {
        item "Beef" 450k for all excluding charlie
        item "Tea" 60k for charlie
        tax 10%
        tip 20k
    }
    """
    ops = _parse_ops(interp, code)
    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, BillOp)
    assert op.title == "BBQ"
    assert op.payer == "alice"
    assert len(op.items) == 2
    assert op.items[0]["for_all"] is True
    assert op.items[0]["excluding"] == ["charlie"]
    assert op.items[1]["consumers"] == ["charlie"]
    assert len(op.modifiers) == 2


def test_possessive_person_query_ast(interp: SplitLangInterpreter):
    ops = _parse_ops(interp, "what is alice's balance?")
    assert isinstance(ops[0], QueryOp)
    assert ops[0].query_kind == "person_balance"
    assert ops[0].target_member == "alice"


def test_settle_aliases_build_same_op(interp: SplitLangInterpreter):
    op1 = _parse_ops(interp, "bob pays alice 100k")[0]
    op2 = _parse_ops(interp, "settle bob to alice 100k")[0]
    assert isinstance(op1, SettleOp) and isinstance(op2, SettleOp)
    assert (op1.from_member, op1.to_member, op1.amount) == (op2.from_member, op2.to_member, op2.amount)
