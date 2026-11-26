"""
Deterministic financial domain logic for SplitLang.

Uses Python's Decimal arithmetic (no IEEE-754 float drift) together with the
Largest-Remainder rounding method (Hamilton method) so that every bill split
sums to the exact total down to the smallest currency unit.
Also implements Greedy Minimum Cash Flow debt simplification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any

from module.Database import Database


ZERO_DECIMAL_CURRENCIES = {"VND", "JPY"}
CURRENCY_SYMBOLS = {
    "VND": "VND",
    "USD": "$",
    "EUR": "€",
    "JPY": "¥",
    "GBP": "£",
    "SGD": "S$",
}


class SemanticError(Exception):
    """Raised when a syntactically valid SplitLang statement violates domain rules."""


def currency_decimals(currency: str) -> int:
    return 0 if currency.upper() in ZERO_DECIMAL_CURRENCIES else 2


def currency_unit(currency: str) -> Decimal:
    return Decimal("1") if currency_decimals(currency) == 0 else Decimal("0.01")


def quantize_money(amount: Decimal, currency: str) -> Decimal:
    unit = currency_unit(currency)
    return amount.quantize(unit, rounding=ROUND_HALF_UP)


def format_money(amount: Decimal, currency: str) -> str:
    cur = currency.upper()
    q = quantize_money(amount, cur)
    if cur == "VND":
        return f"{int(q):,} VND"
    sym = CURRENCY_SYMBOLS.get(cur, f"{cur} ")
    if cur == "JPY":
        return f"{sym}{int(q):,}"
    if q < 0:
        return f"-{sym}{abs(q):,.2f}"
    return f"{sym}{q:,.2f}"


def allocate_largest_remainder(
    total: Decimal,
    weights: dict[str, Decimal],
    currency: str,
) -> dict[str, Decimal]:
    """
    Split `total` proportionally according to `weights`, guaranteeing that
    sum(result.values()) == quantize_money(total, currency) with zero rounding loss.
    """
    if not weights:
        raise SemanticError("Cannot split an expense among 0 participants.")

    total_weight = sum(weights.values(), Decimal("0"))
    if total_weight <= 0:
        raise SemanticError("Total split weight must be positive.")

    unit = currency_unit(currency)
    target_total = quantize_money(total, currency)
    if target_total < 0:
        raise SemanticError("Total amount cannot be negative.")

    exact_shares: dict[str, Decimal] = {}
    floored: dict[str, Decimal] = {}
    remainders: list[tuple[Decimal, int, str]] = []

    for idx, (member, weight) in enumerate(weights.items()):
        exact = (target_total * weight) / total_weight
        floor_val = exact.quantize(unit, rounding=ROUND_DOWN)
        rem = exact - floor_val
        exact_shares[member] = exact
        floored[member] = floor_val
        remainders.append((rem, -idx, member))

    allocated_sum = sum(floored.values(), Decimal("0"))
    leftover_units = int((target_total - allocated_sum) / unit)

    # Distribute leftover smallest units to highest remainders (deterministic tie-break by order)
    remainders.sort(reverse=True)
    result = dict(floored)
    for i in range(leftover_units):
        _, _, member = remainders[i % len(remainders)]
        result[member] += unit

    return result


@dataclass
class ModifierCalc:
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    tip_amount: Decimal
    final_total: Decimal


def compute_modifiers(
    subtotal: Decimal,
    modifiers: list[dict[str, Any]],
    currency: str,
) -> ModifierCalc:
    """
    Apply optional discount, tax, and tip modifiers deterministically.
    Order:
      1. Discount subtracted from subtotal (clamped/validated >= 0)
      2. Tax computed on discounted base (or fixed amount)
      3. Tip computed on discounted base (or fixed amount)
    """
    if subtotal <= 0:
        raise SemanticError("Expense amount must be strictly greater than 0.")

    discount_total = Decimal("0")
    tax_specs: list[dict[str, Any]] = []
    tip_specs: list[dict[str, Any]] = []

    for mod in modifiers:
        kind = mod["kind"]
        if kind == "discount":
            if mod["is_percent"]:
                pct = Decimal(str(mod["value"]))
                if pct < 0 or pct > 100:
                    raise SemanticError(f"Discount percentage must be between 0% and 100% (got {pct}%).")
                discount_total += (subtotal * pct) / Decimal("100")
            else:
                val = Decimal(str(mod["value"]))
                if val < 0:
                    raise SemanticError("Discount amount cannot be negative.")
                discount_total += val
        elif kind == "tax":
            tax_specs.append(mod)
        elif kind == "tip":
            tip_specs.append(mod)

    discount_q = quantize_money(discount_total, currency)
    if discount_q > subtotal:
        raise SemanticError(
            f"Discount ({format_money(discount_q, currency)}) exceeds subtotal "
            f"({format_money(subtotal, currency)})."
        )

    discounted_base = subtotal - discount_q

    tax_total = Decimal("0")
    for mod in tax_specs:
        if mod["is_percent"]:
            pct = Decimal(str(mod["value"]))
            if pct < 0:
                raise SemanticError("Tax percentage cannot be negative.")
            tax_total += (discounted_base * pct) / Decimal("100")
        else:
            val = Decimal(str(mod["value"]))
            if val < 0:
                raise SemanticError("Tax amount cannot be negative.")
            tax_total += val

    tip_total = Decimal("0")
    for mod in tip_specs:
        if mod["is_percent"]:
            pct = Decimal(str(mod["value"]))
            if pct < 0:
                raise SemanticError("Tip percentage cannot be negative.")
            tip_total += (discounted_base * pct) / Decimal("100")
        else:
            val = Decimal(str(mod["value"]))
            if val < 0:
                raise SemanticError("Tip amount cannot be negative.")
            tip_total += val

    tax_q = quantize_money(tax_total, currency)
    tip_q = quantize_money(tip_total, currency)
    subtotal_q = quantize_money(subtotal, currency)
    final_total = subtotal_q - discount_q + tax_q + tip_q

    return ModifierCalc(
        subtotal=subtotal_q,
        discount_amount=discount_q,
        tax_amount=tax_q,
        tip_amount=tip_q,
        final_total=final_total,
    )


def resolve_member_strict(db: Database, group_id: int, raw_name: str) -> str:
    resolved = db.resolve_member_name(group_id, raw_name)
    if not resolved:
        existing = db.list_members(group_id)
        hint = (
            f"Current members: {', '.join(existing)}."
            if existing
            else "No members in this group yet. Use 'add members alice, bob' first."
        )
        raise SemanticError(f"Unknown member '{raw_name}'. {hint}")
    return resolved


def resolve_unique_members(db: Database, group_id: int, raw_names: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in raw_names:
        canonical = resolve_member_strict(db, group_id, name)
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(canonical)
    return ordered


def compute_expense_shares(
    db: Database,
    group_id: int,
    currency: str,
    subtotal: Decimal,
    split_spec: dict[str, Any],
    modifiers: list[dict[str, Any]],
) -> tuple[ModifierCalc, dict[str, Decimal], str]:
    """
    Validate participants & split rules, compute modifiers, and return
    (ModifierCalc, {member: final_share}, canonical_split_mode).
    """
    mod_calc = compute_modifiers(subtotal, modifiers, currency)
    all_members = db.list_members(group_id)
    if not all_members:
        raise SemanticError("Group has no members. Add members first with 'add members alice, bob'.")

    mode = split_spec["mode"]

    if mode == "equal":
        if split_spec.get("among"):
            participants = resolve_unique_members(db, group_id, split_spec["among"])
        elif split_spec.get("excluding"):
            excluded = {
                m.lower() for m in resolve_unique_members(db, group_id, split_spec["excluding"])
            }
            participants = [m for m in all_members if m.lower() not in excluded]
        else:
            participants = list(all_members)

        if not participants:
            raise SemanticError("No participants remain after applying exclusions.")

        weights = {m: Decimal("1") for m in participants}
        shares = allocate_largest_remainder(mod_calc.final_total, weights, currency)
        return mod_calc, shares, "equal"

    if mode == "exact":
        allocs: list[tuple[str, Decimal]] = split_spec["allocations"]
        weights_raw: dict[str, Decimal] = {}
        for raw_person, amt in allocs:
            canonical = resolve_member_strict(db, group_id, raw_person)
            if canonical in weights_raw:
                raise SemanticError(f"Duplicate member '{canonical}' in exact split.")
            if amt < 0:
                raise SemanticError(f"Exact share for '{canonical}' cannot be negative.")
            weights_raw[canonical] = quantize_money(amt, currency)

        alloc_sum = sum(weights_raw.values(), Decimal("0"))
        # Exact shares must match either the subtotal (before tax/tip/discount) or the final total
        if alloc_sum == mod_calc.subtotal and mod_calc.subtotal != mod_calc.final_total:
            shares = allocate_largest_remainder(mod_calc.final_total, weights_raw, currency)
        elif alloc_sum == mod_calc.final_total:
            shares = weights_raw
        else:
            raise SemanticError(
                f"Exact shares sum to {format_money(alloc_sum, currency)}, "
                f"which does not match expense amount {format_money(mod_calc.subtotal, currency)}."
            )
        return mod_calc, shares, "exact"

    if mode == "percent":
        allocs_pct: list[tuple[str, Decimal]] = split_spec["allocations"]
        weights_pct: dict[str, Decimal] = {}
        for raw_person, pct in allocs_pct:
            canonical = resolve_member_strict(db, group_id, raw_person)
            if canonical in weights_pct:
                raise SemanticError(f"Duplicate member '{canonical}' in percentage split.")
            if pct < 0:
                raise SemanticError(f"Percentage for '{canonical}' cannot be negative.")
            weights_pct[canonical] = pct

        total_pct = sum(weights_pct.values(), Decimal("0"))
        if abs(total_pct - Decimal("100")) > Decimal("0.0001"):
            raise SemanticError(
                f"Percentages must sum to 100% (got {total_pct}%)."
            )
        shares = allocate_largest_remainder(mod_calc.final_total, weights_pct, currency)
        return mod_calc, shares, "percent"

    if mode == "ratio":
        allocs_ratio: list[tuple[str, Decimal]] = split_spec["allocations"]
        weights_ratio: dict[str, Decimal] = {}
        for raw_person, ratio in allocs_ratio:
            canonical = resolve_member_strict(db, group_id, raw_person)
            if canonical in weights_ratio:
                raise SemanticError(f"Duplicate member '{canonical}' in ratio split.")
            if ratio <= 0:
                raise SemanticError(f"Ratio weight for '{canonical}' must be positive.")
            weights_ratio[canonical] = ratio

        shares = allocate_largest_remainder(mod_calc.final_total, weights_ratio, currency)
        return mod_calc, shares, "ratio"

    raise SemanticError(f"Unsupported split mode: {mode}")


def compute_bill_shares(
    db: Database,
    group_id: int,
    currency: str,
    items: list[dict[str, Any]],
    modifiers: list[dict[str, Any]],
) -> tuple[ModifierCalc, dict[str, Decimal], list[dict[str, Any]]]:
    """
    Evaluate an itemized bill block:
      - Each item is split equally among its listed consumers (or 'all' / 'all excluding ...').
      - Bill-level discount, tax, and tip are distributed proportionally to each person's
        item subtotal using exact largest-remainder rounding.
    """
    all_members = db.list_members(group_id)
    if not all_members:
        raise SemanticError("Group has no members. Add members first with 'add members alice, bob'.")
    if not items:
        raise SemanticError("An itemized bill must contain at least one item.")

    person_subtotals: dict[str, Decimal] = {}
    resolved_items: list[dict[str, Any]] = []
    bill_subtotal = Decimal("0")

    for item in items:
        amount = quantize_money(Decimal(str(item["amount"])), currency)
        if amount <= 0:
            raise SemanticError(f"Item '{item['name']}' must have a positive amount.")

        if item["for_all"]:
            excluded = {
                m.lower()
                for m in resolve_unique_members(db, group_id, item.get("excluding", []))
            }
            consumers = [m for m in all_members if m.lower() not in excluded]
        else:
            consumers = resolve_unique_members(db, group_id, item["consumers"])

        if not consumers:
            raise SemanticError(f"Item '{item['name']}' has 0 consumers.")

        item_shares = allocate_largest_remainder(
            amount, {c: Decimal("1") for c in consumers}, currency
        )
        for member, sh in item_shares.items():
            person_subtotals[member] = person_subtotals.get(member, Decimal("0")) + sh

        bill_subtotal += amount
        resolved_items.append(
            {
                "name": item["name"],
                "amount": str(amount),
                "consumers": consumers,
                "shares": {k: str(v) for k, v in item_shares.items()},
            }
        )

    mod_calc = compute_modifiers(bill_subtotal, modifiers, currency)
    final_shares = allocate_largest_remainder(mod_calc.final_total, person_subtotals, currency)
    return mod_calc, final_shares, resolved_items


def compute_balances(db: Database, group_id: int) -> list[dict[str, Any]]:
    """
    Compute per-member financial ledger:
      net_balance = total_paid - total_owed + settlements_sent - settlements_received
    Positive net_balance => others owe this person (creditor).
    Negative net_balance => this person owes others (debtor).
    """
    members = db.list_members(group_id)
    ledger: dict[str, dict[str, Decimal]] = {
        m: {
            "paid": Decimal("0"),
            "owed": Decimal("0"),
            "settled_sent": Decimal("0"),
            "settled_received": Decimal("0"),
        }
        for m in members
    }

    for exp in db.list_expenses(group_id):
        payer = exp["payer"]
        if payer not in ledger:
            ledger[payer] = {
                "paid": Decimal("0"),
                "owed": Decimal("0"),
                "settled_sent": Decimal("0"),
                "settled_received": Decimal("0"),
            }
        ledger[payer]["paid"] += exp["total"]
        for member_name, share in exp["shares"].items():
            if member_name not in ledger:
                ledger[member_name] = {
                    "paid": Decimal("0"),
                    "owed": Decimal("0"),
                    "settled_sent": Decimal("0"),
                    "settled_received": Decimal("0"),
                }
            ledger[member_name]["owed"] += share

    for st in db.list_settlements(group_id):
        f_m = st["from_member"]
        t_m = st["to_member"]
        amt = st["amount"]
        if f_m in ledger:
            ledger[f_m]["settled_sent"] += amt
        if t_m in ledger:
            ledger[t_m]["settled_received"] += amt

    rows: list[dict[str, Any]] = []
    for name, data in ledger.items():
        net = (
            data["paid"]
            - data["owed"]
            + data["settled_sent"]
            - data["settled_received"]
        )
        rows.append(
            {
                "member": name,
                "paid": data["paid"],
                "owed": data["owed"],
                "settled_sent": data["settled_sent"],
                "settled_received": data["settled_received"],
                "net": net,
            }
        )
    return rows


def compute_optimal_settlements(
    balances: list[dict[str, Any]],
    currency: str,
) -> list[dict[str, Any]]:
    """
    Greedy Minimum Cash Flow Algorithm (Debt Simplification).

    Repeatedly matches the largest debtor with the largest creditor, settling
    min(|debt|, credit) at each step. Produces at most N - 1 transfers for N
    group members, minimizing transaction count.
    """
    unit = currency_unit(currency)
    creditors: list[list[Any]] = []
    debtors: list[list[Any]] = []

    for row in balances:
        net = quantize_money(row["net"], currency)
        if net >= unit:
            creditors.append([net, row["member"]])
        elif net <= -unit:
            debtors.append([-net, row["member"]])

    transfers: list[dict[str, Any]] = []

    while creditors and debtors:
        # Sort descending by amount, then alphabetically for determinism
        creditors.sort(key=lambda x: (-x[0], x[1].lower()))
        debtors.sort(key=lambda x: (-x[0], x[1].lower()))

        cred_amt, cred_name = creditors[0]
        debt_amt, debt_name = debtors[0]

        transfer_amt = min(cred_amt, debt_amt)
        transfers.append(
            {
                "from": debt_name,
                "to": cred_name,
                "amount": transfer_amt,
                "formatted": format_money(transfer_amt, currency),
            }
        )

        creditors[0][0] -= transfer_amt
        debtors[0][0] -= transfer_amt

        if creditors[0][0] < unit:
            creditors.pop(0)
        if debtors[0][0] < unit:
            debtors.pop(0)

    return transfers


def today_str() -> str:
    return date.today().strftime("%d-%m-%Y")


HELP_TEXT = """SplitLang Quick Grammar Reference
======================================================================
1. Groups & Currency
   group "Da Lat Trip"                 | Switch or create a group
   currency VND                        | Set currency (VND, USD, EUR, JPY, GBP, SGD)
   add members alice, bob, charlie     | Add one or more members
   remove member dave                  | Remove a member

2. Recording Expenses (supports arithmetic: 120k + 30k * 2, $25.50, 1.5m)
   alice paid 300k for dinner
   alice paid 300k for dinner split equally among alice, bob
   alice paid 300k for dinner excluding charlie
   bob paid 150k for coffee split exact alice: 60k, bob: 50k, charlie: 40k
   alice paid 1m for hotel split percent alice: 40%, bob: 30%, charlie: 30%
   charlie paid 400k for hotpot split ratio alice: 2, bob: 1, charlie: 1
   ... with tax 10% with tip 5% with discount 20k on 26-11-2026

3. Itemized Bill Block
   bill "BBQ Night" paid by alice {
       item "Wagyu Beef" 450k for all
       item "Beer Tower" 200k for alice, bob
       item "Matcha Tea" 60k for charlie
       tax 10%
       tip 5%
       discount 50k
   }

4. Settlements & Queries
   bob pays alice 100k                 | Record a repayment
   settle bob to alice 100k            | Alternate repayment syntax
   settle up                           | Optimal min-transfer settlement plan
   show members / balances / expenses / summary / settlements / groups
   who owes whom?                      | List optimal debt transfers
   how much does bob owe?              | Check one person's debt/credit
   what is alice balance?              | Check detailed balance of a member

5. Controls
   undo | reset | help
"""
