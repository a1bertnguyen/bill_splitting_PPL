"""Unit tests for Stage 2 (Lexer) and Stage 3 (Parser) of SplitLang."""

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
        'group "Da Lat Trip"',
        "use group Weekend",
        "currency USD",
        "add members alice, bob, charlie, dave",
        "ADD MEMBER Alice",
        "remove member dave",
        "alice paid 300k",
        "alice paid 300k for dinner",
        "alice paid 120k + 30k * 2 for bun bo hue split equally",
        "alice paid (100k + 50k) * 2 for dinner split equally among alice, bob",
        "alice paid 200k for drinks excluding charlie",
        "bob paid 150k for coffee split exact alice: 60k, bob: 50k, charlie: 40k",
        "alice paid 1.5m for hotel split percent alice: 40%, bob: 30%, charlie: 30%",
        "charlie paid 400k for hotpot split ratio alice: 2, bob: 1, charlie: 1",
        "alice paid $45.50 for lunch with tax 10% with tip 5% with discount $5 on 26-11-2026",
        'bill "BBQ" paid by alice {\n  item "Beef" 450k for all\n  item "Tea" 50k for charlie\n  tax 10%\n}',
        'bill "Drink" paid by bob { item "Beer" 100k for all excluding charlie; tip 10k }',
        "bob pays alice 100k",
        "settle bob to alice 100k for dinner on 26/11/2026",
        "settle up",
        "show members",
        "check balances",
        "show expenses",
        "check summary",
        "show settlements",
        "show groups",
        "who owes whom?",
        "how much does bob owe?",
        "what is alice's balance?",
        "undo",
        "reset",
        "help",
        "// comment only\nadd members alice, bob # trailing comment",
    ],
)
def test_valid_grammar_accepted(interp: SplitLangInterpreter, valid_input: str):
    analysis = interp.analyze(valid_input)
    assert analysis["errors"] == [], f"Unexpected syntax errors for {valid_input!r}: {analysis['errors']}"
    assert len(analysis["tokens"]) > 0


@pytest.mark.parametrize(
    "invalid_input",
    [
        "hello splitlang",
        "alice paid",
        "alice paid for dinner",
        "add members",
        "alice paid 100k split percent",
        "alice paid 100k split exact alice:",
        'bill "Empty" paid by alice { }',
        "currency BTC",
        "show unknown_thing",
        "alice paid 100k + * 50k",
    ],
)
def test_invalid_grammar_rejected(interp: SplitLangInterpreter, invalid_input: str):
    res = interp.execute(invalid_input)
    assert res["ok"] is False
    assert res["stage_failed"] == "lexer_parser"
    assert len(res["errors"]) > 0
