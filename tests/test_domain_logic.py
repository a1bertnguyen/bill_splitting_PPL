"""Unit & integration tests for SplitLang v2.0 Type System, Symbol Table, Set Algebra, & Math."""

from decimal import Decimal
import pytest

from controller.Response import SplitLangInterpreter
from module.utilFunction import compute_balances, compute_optimal_settlements


@pytest.fixture
def interp():
    engine = SplitLangInterpreter(db_path=":memory:")
    yield engine
    engine.close()


def test_symbol_table_set_algebra_and_reusable_rules(interp: SplitLangInterpreter):
    script = """
    workspace "V2 Test" {
        currency: VND
        members: [alice, bob, charlie, dave]
    }
    let vat      = 10%
    let beer     = 60k
    let drinkers = all - [charlie]
    let vip      = [alice] + [bob]
    rule host_w  = ratio { alice: 2, bob: 1, charlie: 1 }

    expense "Beer" paid_by alice = beer * 3 split equal(drinkers)
    expense "Hotpot" {
        payer:  bob
        amount: 400k
        split:  host_w
        tax:    vat
    }
    expense "Dessert" paid_by charlie = 100k split equal(vip)
    assert balanced
    query env
    """
    res = interp.execute(script)
    assert res["ok"] is True

    # Verify Beer split among drinkers = [alice, bob, dave] -> 180k / 3 = 60k each
    beer_shares = {k: Decimal(v) for k, v in res["ops"][6]["result"]["shares"].items()}
    assert beer_shares == {
        "alice": Decimal("60000"),
        "bob": Decimal("60000"),
        "dave": Decimal("60000"),
    }

    # Verify Hotpot with 10% vat = 440k split 2:1:1 -> 220k, 110k, 110k
    hotpot_shares = {k: Decimal(v) for k, v in res["ops"][7]["result"]["shares"].items()}
    assert hotpot_shares == {
        "alice": Decimal("220000"),
        "bob": Decimal("110000"),
        "charlie": Decimal("110000"),
    }

    # Verify query env reports typed Symbol Table
    env_res = res["ops"][-1]["result"]
    assert env_res["variables"]["vat"]["type"] == "PERCENT"
    assert env_res["variables"]["beer"]["type"] == "MONEY"
    assert env_res["variables"]["drinkers"]["type"] == "MEMBER_SET"
    assert "host_w" in env_res["rules"]


def test_dimensional_type_errors_rejected(interp: SplitLangInterpreter):
    interp.execute('workspace "TypeTest" { members: [alice, bob] }')

    # 1. MONEY + PERCENT is a dimensional type error
    r1 = interp.execute("let bad = 100k + 10%")
    assert not r1["ok"] and r1["stage_failed"] == "type_error"
    assert "MONEY and PERCENT" in r1["errors"][0]

    # 2. MONEY * MONEY is a dimensional type error
    r2 = interp.execute("let bad2 = 100k * 50k")
    assert not r2["ok"] and r2["stage_failed"] == "type_error"
    assert "MONEY by MONEY" in r2["errors"][0]

    # 3. equal(100k) expects MEMBER_SET, got MONEY
    r3 = interp.execute('expense "X" paid_by alice = 100k split equal(100k)')
    assert not r3["ok"] and r3["stage_failed"] == "type_error"
    assert "MEMBER_SET" in r3["errors"][0]

    # 4. MONEY * PERCENT IS valid (e.g. 400k * 10% = 40k)
    r4 = interp.execute("let tax_val = 400k * 10%")
    assert r4["ok"] is True
    assert r4["ops"][0]["result"]["value_type"] == "MONEY"
    assert Decimal(r4["ops"][0]["result"]["value"]) == Decimal("40000")


def test_largest_remainder_rounding_vnd_and_usd(interp: SplitLangInterpreter):
    res = interp.execute(
        """
        workspace "VND" { currency: VND; members: [alice, bob, charlie] }
        expense "Lunch" paid_by alice = 100k split equal(all)
        assert balanced
        """
    )
    assert res["ok"] is True
    shares = {k: Decimal(v) for k, v in res["ops"][1]["result"]["shares"].items()}
    assert sum(shares.values()) == Decimal("100000")
    assert sorted(shares.values()) == [Decimal("33333"), Decimal("33333"), Decimal("33334")]

    res_usd = interp.execute(
        """
        workspace "USD" { currency: USD; members: [a, b, c] }
        expense "Coffee" paid_by a = $10 split equal(all)
        assert balanced
        """
    )
    assert res_usd["ok"] is True
    usd_shares = {k: Decimal(v) for k, v in res_usd["ops"][1]["result"]["shares"].items()}
    assert sum(usd_shares.values()) == Decimal("10.00")
    assert sorted(usd_shares.values()) == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]


def test_itemized_bill_proportional_tax_tip_discount(interp: SplitLangInterpreter):
    res = interp.execute(
        """
        workspace "BBQ" { currency: VND; members: [alice, bob, charlie] }
        let vat = 10%
        bill "BBQ" {
            payer: alice
            item "Beef" = 300k for all
            item "Beer" = 200k for [alice, bob]
            item "Tea"  = 100k for [charlie]
            discount: 60k
            tax: vat
        }
        assert balanced
        """
    )
    assert res["ok"] is True
    bill_res = res["ops"][2]["result"]
    assert Decimal(bill_res["subtotal"]) == Decimal("600000")
    assert Decimal(bill_res["total"]) == Decimal("594000")
    shares = {k: Decimal(v) for k, v in bill_res["shares"].items()}
    assert shares == {
        "alice": Decimal("198000"),
        "bob": Decimal("198000"),
        "charlie": Decimal("198000"),
    }


def test_debt_simplification_transfer_and_undo(interp: SplitLangInterpreter):
    res = interp.execute(
        """
        workspace "Chain" { members: [alice, bob, charlie] }
        expense "t1" paid_by alice = 100k split exact { bob: 100k }
        expense "t2" paid_by bob   = 100k split exact { charlie: 100k }
        expense "t3" paid_by charlie = 50k split exact { alice: 50k }
        settle
        """
    )
    assert res["ok"] is True
    transfers = res["ops"][-1]["result"]["transfers"]
    assert len(transfers) == 1
    assert transfers[0]["from"] == "charlie"
    assert transfers[0]["to"] == "alice"
    assert Decimal(transfers[0]["amount"]) == Decimal("50000")

    # Settle via transfer -> then undo
    interp.execute('transfer charlie -> alice = 50k note "done"')
    bal_settled = compute_balances(
        interp.db, interp.ctx.active_group_id, owner_user_id=interp.ctx.owner_user_id
    )
    assert compute_optimal_settlements(bal_settled, "VND") == []

    interp.execute("undo")
    bal_after_undo = compute_balances(
        interp.db, interp.ctx.active_group_id, owner_user_id=interp.ctx.owner_user_id
    )
    assert len(compute_optimal_settlements(bal_after_undo, "VND")) == 1


def test_semantic_errors_caught_cleanly(interp: SplitLangInterpreter):
    interp.execute('workspace "Err" { members: [alice, bob] }')

    # Unknown variable
    r0 = interp.execute('expense "X" paid_by alice = unknown_var')
    assert not r0["ok"] and r0["stage_failed"] == "semantic"

    # Unknown member
    r1 = interp.execute('expense "X" paid_by charlie = 100k')
    assert not r1["ok"] and r1["stage_failed"] == "semantic"

    # Percentages != 100%
    r2 = interp.execute('expense "X" paid_by alice = 100k split percent { alice: 60%, bob: 30% }')
    assert not r2["ok"] and r2["stage_failed"] == "semantic"

    # Division by zero
    r3 = interp.execute('expense "X" paid_by alice = 100k / 0')
    assert not r3["ok"] and r3["stage_failed"] == "semantic"
