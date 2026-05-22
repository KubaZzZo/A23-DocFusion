"""Task-plan models for the server toolkit."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

VALID_LEVELS = {"L1", "L2", "L3"}


def validate_workspace_path(value: str) -> str:
    """Reject absolute paths and path traversal outside the task workspace."""
    if not value:
        raise ValueError("workspace path is required")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(f"path must stay inside workspace: {value}")
    return str(path)


@dataclass(frozen=True)
class TaskStep:
    id: str
    tool: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskStep":
        if not isinstance(data, dict):
            raise ValueError("step must be an object")
        step_id = str(data.get("id") or "").strip()
        tool = str(data.get("tool") or "").strip()
        command = str(data.get("command") or "").strip()
        args = data.get("args") or {}
        if not step_id:
            raise ValueError("step.id is required")
        if not tool:
            raise ValueError("step.tool is required")
        if not command:
            raise ValueError("step.command is required")
        if not isinstance(args, dict):
            raise ValueError("step.args must be an object")
        return cls(id=step_id, tool=tool, command=command, args=dict(args))


@dataclass(frozen=True)
class TaskPlan:
    level: str
    requires_agent: bool
    inputs: list[str]
    outputs: list[str]
    timeout_seconds: int
    steps: list[TaskStep]
    agent_prompt: str | None = None

    @classmethod
    def from_json_file(cls, path: str | Path) -> "TaskPlan":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskPlan":
        if not isinstance(data, dict):
            raise ValueError("task plan must be an object")

        level = str(data.get("level") or "").strip()
        if level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}")

        requires_agent = bool(data.get("requires_agent", False))
        if level == "L3" and not requires_agent:
            raise ValueError("L3 tasks must set requires_agent=true")
        if level in {"L1", "L2"} and requires_agent:
            raise ValueError("L1/L2 tasks must set requires_agent=false")

        inputs = _read_path_list(data, "inputs")
        outputs = _read_path_list(data, "outputs")
        timeout_seconds = int(data.get("timeout_seconds") or 0)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        raw_steps = data.get("steps") or []
        if not isinstance(raw_steps, list):
            raise ValueError("steps must be a list")
        steps = [TaskStep.from_dict(step) for step in raw_steps]

        agent_prompt = data.get("agent_prompt")
        if agent_prompt is not None:
            agent_prompt = str(agent_prompt)

        return cls(
            level=level,
            requires_agent=requires_agent,
            inputs=inputs,
            outputs=outputs,
            timeout_seconds=timeout_seconds,
            steps=steps,
            agent_prompt=agent_prompt,
        )


def _read_path_list(data: dict[str, Any], key: str) -> list[str]:
    raw = data.get(key) or []
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")
    return [validate_workspace_path(str(item)) for item in raw]
