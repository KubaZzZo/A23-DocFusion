"""FastAPI wrapper for the server toolkit task service."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, PlainTextResponse

from server_toolkit.environment_tools import check_environment_tools
from server_toolkit.runners import DockerRunner, LocalRunner
from server_toolkit.task_queue import InMemoryTaskQueue
from server_toolkit.task_service import TaskService
from server_toolkit.plan_parser import PlanUnresolvedError, parse_instruction


def create_app(
    tasks_root: str | Path,
    *,
    max_files: int = 10,
    max_file_size: int = 50 * 1024 * 1024,
    max_total_size: int = 200 * 1024 * 1024,
    allowed_extensions: set[str] | None = None,
    max_concurrent_tasks: int = 1,
    task_queue_size: int = 20,
    bearer_token: str | None = None,
    execution_backend: str | None = None,
) -> FastAPI:
    app = FastAPI(title="DocFusion Server Toolkit API", version="0.1.0")
    service = TaskService(tasks_root)
    backend = execution_backend or os.getenv("DOCFUSION_EXECUTION_BACKEND", "local")
    executor = _build_executor(service, backend)
    task_queue = InMemoryTaskQueue(
        service,
        max_concurrent_tasks=max_concurrent_tasks,
        task_queue_size=task_queue_size,
        executor=executor,
    )
    allowed = allowed_extensions or {"docx", "xlsx", "pptx", "pdf", "txt", "md", "html", "csv", "jpg", "jpeg", "png", "tiff"}
    token = bearer_token if bearer_token is not None else _load_bearer_token()

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not token:
            return
        expected = f"Bearer {token}"
        if authorization != expected:
            raise _api_error(401, "UNAUTHORIZED", "valid Bearer token is required")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "detail": None}},
        )

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "service": "docfusion-server-toolkit"}

    @app.get("/api/server-tools", dependencies=[Depends(require_auth)])
    async def server_tools():
        return {"tools": check_environment_tools()}

    @app.post("/api/server-tasks", status_code=201, dependencies=[Depends(require_auth)])
    async def submit_task(
        plan: Annotated[str | None, Form()] = None,
        instruction: Annotated[str | None, Form()] = None,
        priority: Annotated[str, Form()] = "normal",
        timeout: Annotated[int | None, Form()] = None,
        files: Annotated[list[UploadFile] | None, File()] = None,
    ):
        try:
            if priority not in {"normal", "high"}:
                raise _api_error(400, "INVALID_PRIORITY", "priority must be normal or high")
            temp_paths = []
            with tempfile.TemporaryDirectory() as temp_dir:
                upload_files = files or []
                if len(upload_files) > max_files:
                    raise _api_error(413, "FILE_TOO_LARGE", f"too many files: {len(upload_files)}")
                total_size = 0
                for upload in upload_files:
                    filename = Path(upload.filename or "upload.bin").name
                    suffix = Path(filename).suffix.lower().lstrip(".")
                    if suffix not in allowed:
                        raise _api_error(415, "UNSUPPORTED_TYPE", f"unsupported file type: {suffix}")
                    content = await upload.read()
                    if len(content) > max_file_size:
                        raise _api_error(413, "FILE_TOO_LARGE", f"file too large: {filename}")
                    total_size += len(content)
                    if total_size > max_total_size:
                        raise _api_error(413, "FILE_TOO_LARGE", "total upload size exceeded")
                    path = Path(temp_dir) / filename
                    path.write_bytes(content)
                    temp_paths.append(path)
                if plan:
                    parsed_plan = json.loads(plan)
                elif instruction:
                    input_names = [f"input/{path.name}" for path in temp_paths]
                    parsed_plan = parse_instruction(instruction, input_names)
                else:
                    raise _api_error(400, "PLAN_UNRESOLVED", "plan or instruction is required")
                task_id = f"task_{uuid.uuid4().hex[:12]}"
                task = task_queue.submit(
                    parsed_plan,
                    temp_paths,
                    task_id=task_id,
                    priority=priority,
                    timeout_seconds=timeout,
                )
            return service.get_status(task.task_id)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"invalid plan JSON: {exc}") from exc
        except PlanUnresolvedError as exc:
            raise _api_error(400, "PLAN_UNRESOLVED", str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            if "QUEUE_FULL" in str(exc):
                raise _api_error(429, "QUEUE_FULL", "task queue is full") from exc
            raise

    @app.get("/api/server-tasks", dependencies=[Depends(require_auth)])
    async def list_tasks(status: str = "all", limit: int = 20, offset: int = 0):
        if status not in {"all", "queued", "running", "completed", "failed", "timeout", "cancelled"}:
            raise _api_error(400, "INVALID_STATUS", f"unsupported status: {status}")
        if limit < 1 or limit > 100:
            raise _api_error(400, "INVALID_PAGINATION", "limit must be between 1 and 100")
        if offset < 0:
            raise _api_error(400, "INVALID_PAGINATION", "offset must be greater than or equal to 0")
        return {"tasks": service.list_tasks(status=status, limit=limit, offset=offset)}

    @app.get("/api/server-tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def get_task_status(task_id: str):
        try:
            return service.get_status(task_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/server-tasks/{task_id}/logs", dependencies=[Depends(require_auth)])
    async def get_task_logs(task_id: str):
        try:
            service.get_status(task_id)
            return {"task_id": task_id, "events": service.get_logs(task_id)}
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/server-tasks/{task_id}/events", dependencies=[Depends(require_auth)])
    async def get_task_events(task_id: str):
        try:
            service.get_status(task_id)
            events = service.get_logs(task_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return PlainTextResponse(_format_sse(events), media_type="text/event-stream")

    @app.get("/api/server-tasks/{task_id}/download", dependencies=[Depends(require_auth)])
    async def download_task_result(task_id: str, file: str | None = None):
        try:
            result = service.collect_download(task_id, file_path=file)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        media_type = "application/zip" if result.kind == "zip" else "application/octet-stream"
        return FileResponse(
            result.path,
            media_type=media_type,
            filename=result.path.name,
        )

    @app.delete("/api/server-tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def delete_task(task_id: str):
        try:
            return task_queue.cancel(task_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


def _load_bearer_token() -> str | None:
    env_token = os.getenv("DOCFUSION_API_TOKEN")
    if env_token:
        return env_token

    token_file = os.getenv("DOCFUSION_API_TOKEN_FILE")
    if not token_file:
        return None
    path = Path(token_file)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip()


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, {"error": {"code": code, "message": message, "detail": None}})


def _build_executor(service: TaskService, backend: str):
    normalized = backend.strip().lower()
    if normalized == "local":
        return LocalRunner(service)
    if normalized == "docker-dry-run":
        return DockerRunner(service, dry_run=True)
    if normalized == "docker":
        return DockerRunner(service, dry_run=False)
    raise ValueError(f"unsupported execution backend: {backend}")


def _format_sse(events: list[dict]) -> str:
    lines = []
    lines.append("event: queued")
    lines.append('data: {"event": "queued"}')
    lines.append("")
    for event in events:
        event_name = _event_name(event.get("event"))
        lines.append(f"event: {event_name}")
        lines.append("data: " + json.dumps(event, ensure_ascii=False))
        lines.append("")
    return "\n".join(lines)


def _event_name(raw: object) -> str:
    mapping = {
        "start": "progress",
        "step_started": "step_started",
        "step_completed": "step_completed",
        "complete": "complete",
        "error": "error",
    }
    return mapping.get(str(raw), "progress")
