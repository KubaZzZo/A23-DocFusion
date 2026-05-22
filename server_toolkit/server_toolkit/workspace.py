"""Task workspace helpers for server-side execution."""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TaskWorkspace:
    root: Path

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def task_file(self) -> Path:
        return self.root / "task.json"


@dataclass(frozen=True)
class CollectedResult:
    kind: str
    path: Path


def create_task_workspace(tasks_root: str | Path, task_id: str, input_files: Iterable[str | Path]) -> TaskWorkspace:
    root = Path(tasks_root) / _safe_task_id(task_id)
    workspace = TaskWorkspace(root=root)
    for directory in (workspace.input_dir, workspace.work_dir, workspace.output_dir, workspace.logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    seen_names: set[str] = set()
    for file_path in input_files:
        source = Path(file_path)
        if source.name in seen_names:
            raise ValueError(f"duplicate input filename: {source.name}")
        if not source.is_file():
            raise ValueError(f"input file not found: {source}")
        seen_names.add(source.name)
        shutil.copyfile(source, workspace.input_dir / source.name)
    return workspace


def write_task_plan(workspace: TaskWorkspace, plan: dict[str, Any]) -> Path:
    workspace.root.mkdir(parents=True, exist_ok=True)
    workspace.task_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return workspace.task_file


def collect_results(workspace: TaskWorkspace, file_path: str | None = None) -> CollectedResult:
    if file_path:
        from server_toolkit.task_models import validate_workspace_path

        safe_path = validate_workspace_path(file_path)
        requested = workspace.root / safe_path
        if not requested.is_file() or not requested.resolve().is_relative_to(workspace.output_dir.resolve()):
            raise FileNotFoundError(f"output file not found: {file_path}")
        return CollectedResult(kind="file", path=requested)

    files = [path for path in sorted(workspace.output_dir.rglob("*")) if path.is_file()]
    if not files:
        raise FileNotFoundError("no output files found")
    if len(files) == 1:
        return CollectedResult(kind="file", path=files[0])

    archive_path = workspace.root / "results.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(workspace.output_dir).as_posix())
    return CollectedResult(kind="zip", path=archive_path)


def _safe_task_id(task_id: str) -> str:
    value = str(task_id).strip()
    if not value:
        raise ValueError("task_id is required")
    if any(char in value for char in ("\\", "/", ":", "..")):
        raise ValueError(f"unsafe task_id: {task_id}")
    return value
