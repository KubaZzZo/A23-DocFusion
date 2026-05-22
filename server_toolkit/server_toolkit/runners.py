"""Execution backend abstractions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from server_toolkit.docker_runtime import build_docker_command
from server_toolkit.task_service import TaskService
from server_toolkit.worker import ExecutionResult

CommandRunner = Callable[[list[str], int], tuple[int, str, str]]


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
    def __init__(
        self,
        service: TaskService,
        *,
        dry_run: bool = True,
        command_runner: CommandRunner | None = None,
    ):
        self.service = service
        self.dry_run = dry_run
        self.command_runner = command_runner or _run_subprocess

    def run(self, task_id: str) -> DockerRunResult:
        workspace = self.service.get_workspace(task_id)
        status = self.service.get_status(task_id)
        command = build_docker_command(task_id, workspace, level=status["level"])
        if self.dry_run:
            return DockerRunResult(success=True, command=command)
        status.update(
            {
                "status": "running",
                "started_at": status.get("started_at") or self.service.now(),
                "error": None,
            }
        )
        self.service._write_status(workspace, status)
        timeout = int(status.get("timeout_seconds") or 60)
        try:
            return_code, stdout, stderr = self.command_runner(command, timeout)
        except TimeoutError as exc:
            status = self.service.get_status(task_id)
            status.update(
                {
                    "status": "timeout",
                    "completed_at": self.service.now(),
                    "error": str(exc),
                }
            )
            self.service._write_status(workspace, status)
            return DockerRunResult(success=False, command=command, error=str(exc))
        if return_code == 0:
            files = sorted(path.relative_to(workspace.root).as_posix() for path in workspace.output_dir.rglob("*") if path.is_file())
            status = self.service.get_status(task_id)
            status.update(
                {
                    "status": "completed",
                    "completed_at": self.service.now(),
                    "output_files": files,
                    "error": None,
                }
            )
            self.service._write_status(workspace, status)
            return DockerRunResult(success=True, command=command)
        error = stderr or stdout or f"docker worker exited with code {return_code}"
        status = self.service.get_status(task_id)
        status.update(
            {
                "status": "failed",
                "completed_at": self.service.now(),
                "error": error,
            }
        )
        self.service._write_status(workspace, status)
        return DockerRunResult(success=False, command=command, error=error)


def _run_subprocess(command: list[str], timeout: int) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"docker worker timed out after {timeout}s") from exc
    return completed.returncode, completed.stdout, completed.stderr
