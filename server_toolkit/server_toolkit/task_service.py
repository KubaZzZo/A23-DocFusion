"""Small task service for local server-toolkit execution."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from server_toolkit.task_models import TaskPlan
from server_toolkit.worker import ExecutionResult, execute_plan
from server_toolkit.workspace import (
    CollectedResult,
    TaskWorkspace,
    collect_results,
    create_task_workspace,
    write_task_plan,
)


@dataclass(frozen=True)
class SubmittedTask:
    task_id: str
    workspace: TaskWorkspace
    status: str


class TaskService:
    """Create, run, and inspect task workspaces.

    This class is intentionally synchronous. API and queue layers can wrap it
    without changing the underlying task/workspace contract.
    """

    def __init__(self, tasks_root: str | Path):
        self.tasks_root = Path(tasks_root)
        self.tasks_root.mkdir(parents=True, exist_ok=True)

    def submit(
        self,
        plan: dict[str, Any],
        input_files: Iterable[str | Path],
        *,
        task_id: str,
        priority: str = "normal",
        timeout_seconds: int | None = None,
    ) -> SubmittedTask:
        validated_plan = TaskPlan.from_dict(plan)
        copied_files = [Path(file_path) for file_path in input_files]
        effective_timeout = int(timeout_seconds or validated_plan.timeout_seconds)
        plan = dict(plan)
        plan["timeout_seconds"] = effective_timeout
        workspace = create_task_workspace(self.tasks_root, task_id, copied_files)
        write_task_plan(workspace, plan)
        self._write_status(
            workspace,
            {
                "task_id": task_id,
                "status": "queued",
                "level": plan["level"],
                "requires_agent": bool(plan.get("requires_agent", False)),
                "priority": priority,
                "timeout_seconds": effective_timeout,
                "created_at": _now(),
                "started_at": None,
                "completed_at": None,
                "progress": {
                    "current_step": 0,
                    "total_steps": len(validated_plan.steps),
                    "description": "queued",
                },
                "input_files": [path.name for path in copied_files],
                "output_files": [],
                "error": None,
            },
        )
        return SubmittedTask(task_id=task_id, workspace=workspace, status="queued")

    def run_local(self, task_id: str) -> ExecutionResult:
        workspace = self.get_workspace(task_id)
        status = self.get_status(task_id)
        total_steps = int(status.get("progress", {}).get("total_steps") or 0)
        status.update(
            {
                "status": "running",
                "started_at": _now(),
                "error": None,
                "progress": {
                    "current_step": 0,
                    "total_steps": total_steps,
                    "description": "running",
                },
            }
        )
        self._write_status(workspace, status)

        result = execute_plan(workspace.task_file, workspace.root)
        status = self.get_status(task_id)
        final_status = "completed" if result.success else "failed"
        status.update(
            {
                "status": final_status,
                "completed_at": _now(),
                "progress": {
                    "current_step": total_steps if result.success else 0,
                    "total_steps": total_steps,
                    "description": final_status,
                },
                "output_files": result.files,
                "error": result.error,
            }
        )
        self._write_status(workspace, status)
        return result

    def get_workspace(self, task_id: str) -> TaskWorkspace:
        workspace = TaskWorkspace(root=self.tasks_root / task_id)
        if not workspace.root.exists():
            raise FileNotFoundError(f"task not found: {task_id}")
        return workspace

    def get_status(self, task_id: str) -> dict[str, Any]:
        workspace = self.get_workspace(task_id)
        status_file = workspace.root / "status.json"
        if not status_file.exists():
            raise FileNotFoundError(f"status not found: {task_id}")
        return json.loads(status_file.read_text(encoding="utf-8"))

    def get_logs(self, task_id: str) -> list[dict[str, Any]]:
        workspace = self.get_workspace(task_id)
        log_file = workspace.logs_dir / "steps.jsonl"
        if not log_file.exists():
            return []
        events = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def collect_download(self, task_id: str, file_path: str | None = None) -> CollectedResult:
        return collect_results(self.get_workspace(task_id), file_path=file_path)

    def list_tasks(self, status: str = "all", limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        tasks = []
        for status_file in sorted(self.tasks_root.glob("*/status.json")):
            task_status = json.loads(status_file.read_text(encoding="utf-8"))
            if status != "all" and task_status.get("status") != status:
                continue
            tasks.append(task_status)
        return tasks[offset: offset + limit]

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        workspace = self.get_workspace(task_id)
        status = self.get_status(task_id)
        status.update(
            {
                "status": "cancelled",
                "completed_at": _now(),
                "error": None,
            }
        )
        self._write_status(workspace, status)
        return status

    def cleanup_expired_tasks(
        self,
        *,
        now: datetime | None = None,
        completed_ttl: timedelta = timedelta(hours=24),
        failed_ttl: timedelta = timedelta(hours=72),
        timeout_ttl: timedelta = timedelta(hours=72),
        cancelled_ttl: timedelta = timedelta(hours=24),
    ) -> list[str]:
        current_time = now or datetime.now(timezone.utc)
        ttl_by_status = {
            "completed": completed_ttl,
            "failed": failed_ttl,
            "timeout": timeout_ttl,
            "cancelled": cancelled_ttl,
        }
        removed: list[str] = []
        for status_file in sorted(self.tasks_root.glob("*/status.json")):
            try:
                status = json.loads(status_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            ttl = ttl_by_status.get(str(status.get("status")))
            completed_at = status.get("completed_at")
            if ttl is None or not completed_at:
                continue
            finished_at = datetime.fromisoformat(str(completed_at))
            if current_time - finished_at > ttl:
                task_id = str(status.get("task_id") or status_file.parent.name)
                shutil.rmtree(status_file.parent)
                removed.append(task_id)
        return removed

    @staticmethod
    def now() -> str:
        return _now()

    @staticmethod
    def _write_status(workspace: TaskWorkspace, status: dict[str, Any]) -> None:
        status_file = workspace.root / "status.json"
        temp_file = workspace.root / "status.json.tmp"
        temp_file.write_text(
            json.dumps(status, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(status_file)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
