"""Execution backend abstractions."""

from __future__ import annotations

from dataclasses import dataclass

from server_toolkit.docker_runtime import build_docker_command
from server_toolkit.task_service import TaskService
from server_toolkit.worker import ExecutionResult


@dataclass(frozen=True)
class DockerRunResult:
    success: bool
    command: list[str]
    error: str | None = None


class LocalRunner:
    def __init__(self, service: TaskService):
        self.service = service

    def run(self, task_id: str) -> ExecutionResult:
        return self.service.run_local(task_id)


class DockerRunner:
    def __init__(self, service: TaskService, *, dry_run: bool = True):
        self.service = service
        self.dry_run = dry_run

    def run(self, task_id: str) -> DockerRunResult:
        workspace = self.service.get_workspace(task_id)
        status = self.service.get_status(task_id)
        command = build_docker_command(task_id, workspace, level=status["level"])
        if self.dry_run:
            return DockerRunResult(success=True, command=command)
        raise RuntimeError("Docker execution is not implemented; use dry_run=True")
