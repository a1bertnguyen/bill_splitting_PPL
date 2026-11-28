"""
Authenticated & Row-Level-Secured Workspace / DSL Router (/api/state, /api/execute, /api/demo, /api/upload).

Enforces Controls #4, #6, #7, #8, #9, #14, #16, #17.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from backend.core.dependencies import (
    client_ip,
    get_current_session,
    get_user_interpreter,
    require_csrf,
)
from backend.core.security import validate_split_upload
from backend.schemas.api_schemas import DemoRequest, ExecuteRequest, UploadResponse

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"

DEMO_FILES = {
    "dinner": EXAMPLES_DIR / "dinner_demo.split",
    "trip": EXAMPLES_DIR / "usd_trip_demo.split",
}

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/state")
def get_state(
    request: Request,
    session: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    interp = get_user_interpreter(request, session["user_id"])
    return interp.get_dashboard_state()


@router.post("/groups/{group_id}/select")
def select_group(
    group_id: int,
    request: Request,
    session: dict[str, Any] = Depends(require_csrf),
) -> dict[str, Any]:
    interp = get_user_interpreter(request, session["user_id"], requested_group_id=group_id)
    return interp.get_dashboard_state()


@router.post("/execute")
def execute_code(
    req: ExecuteRequest,
    request: Request,
    session: dict[str, Any] = Depends(require_csrf),
) -> dict[str, Any]:
    state = request.app.state
    allowed, retry_after = state.api_limiter.check(f"exec:{session['user_id']}:{client_ip(request)}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Slow down.",
            headers={"Retry-After": str(retry_after)},
        )
    interp = get_user_interpreter(request, session["user_id"], requested_group_id=req.group_id)
    result = interp.execute(req.code)
    state.active_groups[session["user_id"]] = interp.ctx.active_group_id
    return {
        "execution": result,
        "state": interp.get_dashboard_state(),
    }


@router.post("/demo")
def run_demo(
    req: DemoRequest,
    request: Request,
    session: dict[str, Any] = Depends(require_csrf),
) -> dict[str, Any]:
    demo_path = DEMO_FILES.get(req.name)
    if not demo_path or not demo_path.is_file():
        raise HTTPException(status_code=404, detail="Demo not found.")
    code = demo_path.read_text(encoding="utf-8")
    interp = get_user_interpreter(request, session["user_id"])
    result = interp.execute(code)
    request.app.state.active_groups[session["user_id"]] = interp.ctx.active_group_id
    return {
        "code": code,
        "execution": result,
        "state": interp.get_dashboard_state(),
    }


# Control #16: Restricted in-memory .split file upload
@router.post("/upload", response_model=UploadResponse)
async def upload_split_file(
    file: UploadFile = File(...),
    _session: dict[str, Any] = Depends(require_csrf),
):
    raw_bytes = await file.read(65537)  # Read at most 64KB + 1 byte
    try:
        clean_name, decoded = validate_split_upload(file.filename, raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(filename=clean_name, code=decoded, size_bytes=len(raw_bytes))
