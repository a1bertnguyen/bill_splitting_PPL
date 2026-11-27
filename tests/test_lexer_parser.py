"""Unit tests for Stage 2 (Lexer) and Stage 3 (Parser) of SplitLang v2.0."""

import pytest
from controller.Response import SplitLangInterpreter


@pytest.fixture
def interp():
    engine = SplitLangInterpreter(db_path=":memory:")
    yield engine
    engine.close()


@pytest.mark.parametrize(
    "valid_input",
    [
        'workspace "Da Lat Trip"',
        'workspace "Trip" {\n  currency: USD\n  members: [alice, bob, charlie]\n}',
        "currency VND",
        "member add [alice, bob, charlie, dave]",
        "member remove [dave]",
        "let vat = 10%",
        "let beer = 60k",
        "let total = 120k + 30k * 4",
        "let neg = -50k",
        "let drinkers = all - [charlie]",
        "let combined = drinkers + [eve]",
        "rule host_w = ratio { alice: 2, bob: 1, charlie: 1 }",
        "rule even_ab = equal([alice, bob])",
        'expense "Dinner" paid_by alice = 300k',
        'expense "Grab" paid_by alice = (100k + 50k) * 2 split equal(all - [dave]) tax 10% on 2026-11-26',
        'expense "Hotpot" {\n  payer: alice\n  amount: 400k\n  split: host_w\n  discount: 50k\n  tax: vat\n  tip: 5%\n  date: 2026-11-26\n}',
        'expense "Coffee" {\n  payer: bob\n  amount: 150k\n  split: exact { alice: 60k, bob: 50k, charlie: 40k }\n}',
        'expense "Hotel" {\n  payer: alice\n  amount: 1.5m\n  split: percent { alice: 40%, bob: 30%, charlie: 30% }\n}',
        'bill "BBQ" {\n  payer: bob\n  item "Beef" = 480k for all\n  item "Beer" = 60k * 4 for all - [charlie]\n  discount: 60k\n  tax: 10%\n  tip: 5%\n}',
        'transfer dave -> alice = 100k note "payback" on 2026-11-26',
        "assert balanced",
        "query summary",
        "query balances",
        "query balance(alice)",
        "query expenses",
        "query members",
        "query groups",
        "query env",
        "settle",
        "undo",
        "reset",
        "help",
        "/* block comment */\n// line comment\nmember add [alice, bob]",
    ],
)
def test_valid_v2_grammar_accepted(interp: SplitLangInterpreter, valid_input: str):
    analysis = interp.analyze(valid_input)
    assert analysis["errors"] == [], f"Unexpected syntax errors for {valid_input!r}: {analysis['errors']}"
    assert len(analysis["tokens"]) > 0


@pytest.mark.parametrize(
    "invalid_input",
    [
        "hello splitlang",
        "expense broken syntax",
        'expense "Dinner" paid_by alice =',
        "member add []",
        "let 123 = 50k",
        "transfer alice => bob = 50k",
        "currency BTC",
        "query unknown_table",
        'expense "Bad" paid_by alice = 100k + * 50k',
        'bill "Empty" {}',
    ],
)
def test_invalid_v2_grammar_rejected(interp: SplitLangInterpreter, invalid_input: str):
    res = interp.execute(invalid_input)
    assert res["ok"] is False
    assert res["stage_failed"] == "lexer_parser"
    assert len(res["errors"]) > 0
