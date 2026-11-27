"""
FastAPI Backend for SplitLang Web Frontend.

Exposes REST endpoints wrapping the 5-stage ANTLR 4.9.2 SplitLangInterpreter
and serves the static Web Frontend from frontend/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from controller.Response import SplitLangInterpreter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

DEMO_FILES = {
    "dinner": EXAMPLES_DIR / "dinner_demo.split",
    "trip": EXAMPLES_DIR / "usd_trip_demo.split",
}


class ExecuteRequest(BaseModel):
    code: str


class DemoRequest(BaseModel):
    name: str = "dinner"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="SplitLang — Bill-Splitting Custom DSL API",
        version="1.0.0",
    )
    interpreter = SplitLangInterpreter(db_path=db_path)
    app.state.interpreter = interpreter

    # ------------------------------------------------------------------
    # REST API Endpoints
    # ------------------------------------------------------------------

    @app.get("/api/state")
    def get_state() -> dict[str, Any]:
        return interpreter.get_dashboard_state()

    @app.post("/api/execute")
    def execute_code(req: ExecuteRequest) -> dict[str, Any]:
        result = interpreter.execute(req.code)
        return {
            "execution": result,
            "state": interpreter.get_dashboard_state(),
        }

    @app.post("/api/demo")
    def run_demo(req: DemoRequest) -> dict[str, Any]:
        demo_path = DEMO_FILES.get(req.name)
        if not demo_path or not demo_path.is_file():
            raise HTTPException(status_code=404, detail=f"Demo '{req.name}' not found.")
        code = demo_path.read_text(encoding="utf-8")
        result = interpreter.execute(code)
        return {
            "code": code,
            "execution": result,
            "state": interpreter.get_dashboard_state(),
        }

    @app.get("/api/demos")
    def list_demos() -> dict[str, Any]:
        return {
            "demos": [
                {"id": "dinner", "label": "Saigon Weekend (VND)"},
                {"id": "trip", "label": "Tokyo Trip (USD)"},
            ]
        }

    # ------------------------------------------------------------------
    # Static Frontend Files
    # ------------------------------------------------------------------

    if FRONTEND_DIR.is_dir():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

        @app.get("/")
        def serve_index():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
