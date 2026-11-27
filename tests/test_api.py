"""API & Web Frontend integration tests for FastAPI backend routes & static assets."""

from pathlib import Path
import pytest

from api.server import DemoRequest, ExecuteRequest, FRONTEND_DIR, create_app


def _get_endpoint(app, path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"Route {method} {path} not registered")


@pytest.fixture
def web_app():
    app = create_app(db_path=":memory:")
    yield app
    app.state.interpreter.close()


def test_frontend_assets_exist_and_index_served(web_app):
    serve_index = _get_endpoint(web_app, "/", "GET")
    resp = serve_index()
    assert Path(resp.path).is_file()
    html = Path(resp.path).read_text(encoding="utf-8")
    assert "SplitLang" in html

    for rel in ("css/styles.css", "js/app.js", "js/render.js", "js/api.js"):
        assert (FRONTEND_DIR / rel).is_file(), f"Missing frontend asset: {rel}"


def test_execute_and_dashboard_state(web_app):
    execute_ep = _get_endpoint(web_app, "/api/execute", "POST")
    state_ep = _get_endpoint(web_app, "/api/state", "GET")

    payload = execute_ep(
        ExecuteRequest(
            code=(
                "add members alice, bob, charlie\n"
                'bob paid 120k + 30k * 2 for "Hotpot" split ratio alice: 2, bob: 1, charlie: 1 with tax 10%'
            )
        )
    )
    assert payload["execution"]["ok"] is True
    assert len(payload["execution"]["tokens"]) > 0
    assert "ExpenseOp" in payload["execution"]["ast_tree"]

    state = state_ep()
    assert state["total_spent"] == "198,000 VND"
    assert len(state["members"]) == 3
    assert len(state["transfers"]) == 2


def test_demo_endpoint_and_errors(web_app):
    demo_ep = _get_endpoint(web_app, "/api/demo", "POST")
    execute_ep = _get_endpoint(web_app, "/api/execute", "POST")

    demo = demo_ep(DemoRequest(name="dinner"))
    assert demo["execution"]["ok"] is True
    assert demo["state"]["expense_count"] == 6

    bad_syntax = execute_ep(ExecuteRequest(code="hello splitlang"))
    assert bad_syntax["execution"]["ok"] is False
    assert bad_syntax["execution"]["stage_failed"] == "lexer_parser"

    bad_semantic = execute_ep(
        ExecuteRequest(code="alice paid 100k for snacks split percent alice: 60%, bob: 30%")
    )
    assert bad_semantic["execution"]["ok"] is False
    assert bad_semantic["execution"]["stage_failed"] == "semantic"
