"""Local worker executor for server toolkit task plans."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server_toolkit.task_models import TaskPlan, validate_workspace_path
from server_toolkit.tools import ToolError, run_tool


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    files: list[str]
    error: str | None = None


def execute_plan(task_file: str | Path, workspace: str | Path) -> ExecutionResult:
    workspace_path = Path(workspace).resolve()
    _ensure_workspace_dirs(workspace_path)
    logs_path = workspace_path / "logs" / "steps.jsonl"
    plan = TaskPlan.from_json_file(task_file)

    _log(logs_path, "start", level=plan.level, requires_agent=plan.requires_agent)
    try:
        if plan.requires_agent:
            raise ToolError("Codex agent execution is planned but not implemented in this toolkit slice")

        for index, step in enumerate(plan.steps, start=1):
            if step.tool != "docfusion":
                raise ToolError(f"Unsupported tool: {step.tool}")
            _log(logs_path, "step_started", step=step.id, index=index, command=step.command)
            args = _resolve_args(step.args, workspace_path)
            result = run_tool(step.command, args)
            _log(logs_path, "step_completed", step=step.id, index=index, command=step.command, result=result)

        _verify_declared_outputs(workspace_path, plan.outputs)
        files = _collect_outputs(workspace_path)
        _log(logs_path, "complete", files=files)
        return ExecutionResult(success=True, files=files)
    except Exception as exc:
        error = str(exc)
        _log(logs_path, "error", error=error)
        return ExecutionResult(success=False, files=_collect_outputs(workspace_path), error=error)


def _ensure_workspace_dirs(workspace: Path) -> None:
    for name in ("input", "work", "output", "logs"):
        (workspace / name).mkdir(parents=True, exist_ok=True)


def _resolve_args(args: dict[str, Any], workspace: Path) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in args.items():
        if key in {"input", "output", "data"} and isinstance(value, str):
            resolved[key] = str(_resolve_workspace_path(workspace, value))
        elif key == "inputs" and isinstance(value, list):
            resolved[key] = [str(_resolve_workspace_path(workspace, str(item))) for item in value]
        else:
            resolved[key] = value
    return resolved


def _resolve_workspace_path(workspace: Path, value: str) -> Path:
    safe = validate_workspace_path(value)
    return workspace / safe


def _collect_outputs(workspace: Path) -> list[str]:
    output_dir = workspace / "output"
    if not output_dir.exists():
        return []
    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            files.append(path.relative_to(workspace).as_posix())
    return files


def _verify_declared_outputs(workspace: Path, outputs: list[str]) -> None:
    missing = []
    for output in outputs:
        path = workspace / validate_workspace_path(output)
        if not path.exists():
            missing.append(output)
    if missing:
        raise ToolError(f"declared output missing: {', '.join(missing)}")


def _log(path: Path, event: str, **payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "time": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
