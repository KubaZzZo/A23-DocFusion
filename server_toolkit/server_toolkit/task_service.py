"""Small task service for local server-toolkit execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
    ) -> SubmittedTask:
        TaskPlan.from_dict(plan)
        workspace = create_task_workspace(self.tasks_root, task_id, input_files)
        write_task_plan(workspace, plan)
        self._write_status(
            workspace,
            {
                "task_id": task_id,
                "status": "queued",
                "level": plan["level"],
                "requires_agent": bool(plan.get("requires_agent", False)),
                "created_at": _now(),
                "started_at": None,
                "completed_at": None,
                "output_files": [],
                "error": None,
            },
        )
        return SubmittedTask(task_id=task_id, workspace=workspace, status="queued")

    def run_local(self, task_id: str) -> ExecutionResult:
        workspace = self.get_workspace(task_id)
        status = self.get_status(task_id)
        status.update({"status": "running", "started_at": _now(), "error": None})
        self._write_status(workspace, status)

        result = execute_plan(workspace.task_file, workspace.root)
        status = self.get_status(task_id)
        status.update(
            {
                "status": "completed" if result.success else "failed",
                "completed_at": _now(),
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

    def collect_download(self, task_id: str) -> CollectedResult:
        return collect_results(self.get_workspace(task_id))

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
