"""Unit & integration tests for Stage 5 (Financial Engine, Semantics, Debt Simplification)."""

from decimal import Decimal
import pytest

from controller.Response import SplitLangInterpreter
from module.utilFunction import compute_balances, compute_optimal_settlements


@pytest.fixture
def interp():
    engine = SplitLangInterpreter(db_path=":memory:")
    yield engine
    engine.close()


def test_largest_remainder_rounding_vnd_and_usd(interp: SplitLangInterpreter):
    # VND: 100,000 / 3 -> 33,334 + 33,333 + 33,333 == 100,000 (0 dong lost!)
    res = interp.execute(
        """
        currency VND
        add members alice, bob, charlie
        alice paid 100k for lunch split equally
        """
    )
    assert res["ok"] is True
    shares = {k: Decimal(v) for k, v in res["ops"][-1]["result"]["shares"].items()}
    assert sum(shares.values()) == Decimal("100000")
    assert sorted(shares.values()) == [Decimal("33333"), Decimal("33333"), Decimal("33334")]

    # USD: $10.00 / 3 -> $3.34 + $3.33 + $3.33 == $10.00 (0 cents lost!)
    res_usd = interp.execute(
        """
        group "US Trip"
        currency USD
        add members a, b, c
        a paid $10 for coffee split equally
        """
    )
    assert res_usd["ok"] is True
    usd_shares = {k: Decimal(v) for k, v in res_usd["ops"][-1]["result"]["shares"].items()}
    assert sum(usd_shares.values()) == Decimal("10.00")
    assert sorted(usd_shares.values()) == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]


def test_all_four_split_modes_and_modifiers(interp: SplitLangInterpreter):
    script = """
    add members alice, bob, charlie
    alice paid 300k for dinner split equally
    bob paid 150k for coffee split exact alice: 60k, bob: 50k, charlie: 40k
    charlie paid 1m for hotel split percent alice: 40%, bob: 30%, charlie: 30%
    alice paid 400k for hotpot split ratio alice: 2, bob: 1, charlie: 1 with tax 10%
    """
    res = interp.execute(script)
    assert res["ok"] is True

    # Hotpot with 10% tax: 400k + 40k = 440k -> ratio 2:1:1 => 220k, 110k, 110k
    hotpot_shares = {k: Decimal(v) for k, v in res["ops"][-1]["result"]["shares"].items()}
    assert hotpot_shares == {
        "alice": Decimal("220000"),
        "bob": Decimal("110000"),
        "charlie": Decimal("110000"),
    }

    # Ledger zero-sum invariant: sum of all net balances MUST equal 0
    balances = compute_balances(interp.db, interp.ctx.active_group_id)
    assert sum(b["net"] for b in balances) == Decimal("0")


def test_itemized_bill_proportional_tax_tip_discount(interp: SplitLangInterpreter):
    script = """
    add members alice, bob, charlie
    bill "BBQ" paid by alice {
        item "Beef" 300k for all
        item "Beer" 200k for alice, bob
        item "Tea" 100k for charlie
        discount 60k
        tax 10%
    }
    """
    res = interp.execute(script)
    assert res["ok"] is True
    bill_res = res["ops"][-1]["result"]
    # Subtotal = 600k; discount = 60k -> 540k; tax 10% = 54k -> final = 594k
    assert Decimal(bill_res["subtotal"]) == Decimal("600000")
    assert Decimal(bill_res["discount"]) == Decimal("60000")
    assert Decimal(bill_res["tax"]) == Decimal("54000")
    assert Decimal(bill_res["total"]) == Decimal("594000")

    # Item subtotals: alice = 100k + 100k = 200k, bob = 100k + 100k = 200k, charlie = 100k + 100k = 200k
    # So each person's proportional share of 594k is exactly 198k!
    shares = {k: Decimal(v) for k, v in bill_res["shares"].items()}
    assert shares == {
        "alice": Decimal("198000"),
        "bob": Decimal("198000"),
        "charlie": Decimal("198000"),
    }


def test_debt_simplification_minimum_transfers(interp: SplitLangInterpreter):
    # Classic circular chain: A pays for B (100k), B pays for C (100k), C pays for A (50k)
    # Net: A = +50k, B = 0, C = -50k -> simplifies to JUST 1 transfer: C -> A 50k!
    script = """
    add members alice, bob, charlie
    alice paid 100k for t1 split exact bob: 100k
    bob paid 100k for t2 split exact charlie: 100k
    charlie paid 50k for t3 split exact alice: 50k
    settle up
    """
    res = interp.execute(script)
    assert res["ok"] is True
    transfers = res["ops"][-1]["result"]["transfers"]
    assert len(transfers) == 1
    assert transfers[0]["from"] == "charlie"
    assert transfers[0]["to"] == "alice"
    assert Decimal(transfers[0]["amount"]) == Decimal("50000")


def test_repayment_reduces_debt_and_undo_reverses(interp: SplitLangInterpreter):
    interp.execute(
        """
        add members alice, bob
        alice paid 200k for dinner split equally
        bob pays alice 100k
        """
    )
    balances = compute_balances(interp.db, interp.ctx.active_group_id)
    transfers = compute_optimal_settlements(balances, "VND")
    assert transfers == []

    # Undo the repayment -> Bob owes Alice 100k again
    undo_res = interp.execute("undo")
    assert undo_res["ok"] is True
    balances_after = compute_balances(interp.db, interp.ctx.active_group_id)
    transfers_after = compute_optimal_settlements(balances_after, "VND")
    assert len(transfers_after) == 1
    assert transfers_after[0]["from"] == "bob"
    assert transfers_after[0]["amount"] == Decimal("100000")


def test_semantic_errors_caught_cleanly(interp: SplitLangInterpreter):
    interp.execute("add members alice, bob")

    # 1. Unknown member
    r1 = interp.execute("charlie paid 100k for lunch")
    assert not r1["ok"] and r1["stage_failed"] == "semantic"
    assert "Unknown member" in r1["errors"][0]

    # 2. Percentages not summing to 100%
    r2 = interp.execute("alice paid 100k for lunch split percent alice: 60%, bob: 30%")
    assert not r2["ok"] and r2["stage_failed"] == "semantic"
    assert "100%" in r2["errors"][0]

    # 3. Exact amounts not matching total
    r3 = interp.execute("alice paid 100k for lunch split exact alice: 40k, bob: 40k")
    assert not r3["ok"] and r3["stage_failed"] == "semantic"
    assert "does not match" in r3["errors"][0]

    # 4. Division by zero in expression
    r4 = interp.execute("alice paid 100k / 0 for lunch")
    assert not r4["ok"] and r4["stage_failed"] == "semantic"
    assert "Division by zero" in r4["errors"][0]

    # 5. Self settlement
    r5 = interp.execute("alice pays alice 50k")
    assert not r5["ok"] and r5["stage_failed"] == "semantic"
