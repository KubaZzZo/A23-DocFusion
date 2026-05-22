"""Docker command construction for isolated server workers.

This module deliberately builds argv lists only; it does not start Docker.
The API is meant to be consumed by a later scheduler/API layer.
"""

from __future__ import annotations

from pathlib import Path

from server_toolkit.workspace import TaskWorkspace


def build_docker_command(
    task_id: str,
    workspace: TaskWorkspace,
    *,
    level: str,
    worker_image: str = "docfusion-worker:latest",
    agent_image: str = "docfusion-agent:latest",
    api_key_env: str | None = None,
) -> list[str]:
    """Build a safe docker run argv for an L1/L2 worker or L3 agent worker."""
    normalized_level = level.upper()
    if normalized_level in {"L1", "L2"}:
        return _base_command(
            task_id=task_id,
            workspace=workspace,
            container_name_prefix="docfusion-task",
            memory="2g",
            cpus="1.5",
            pids_limit="100",
            network="none",
            image=worker_image,
            entrypoint="/entrypoint.sh",
        )
    if normalized_level == "L3":
        if not api_key_env:
            raise ValueError("api_key_env is required for L3 Codex workers")
        command = _base_command(
            task_id=task_id,
            workspace=workspace,
            container_name_prefix="docfusion-agent",
            memory="4g",
            cpus="2",
            pids_limit="150",
            network="docfusion-llm-only",
            image=agent_image,
            entrypoint="/entrypoint-agent.sh",
        )
        image_index = command.index(agent_image)
        command[image_index:image_index] = ["-e", f"OPENAI_API_KEY=${{{api_key_env}}}"]
        return command
    raise ValueError(f"unsupported task level: {level}")


def _base_command(
    *,
    task_id: str,
    workspace: TaskWorkspace,
    container_name_prefix: str,
    memory: str,
    cpus: str,
    pids_limit: str,
    network: str,
    image: str,
    entrypoint: str,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        f"{container_name_prefix}-{task_id}",
        "--user",
        "1000:1000",
        "--memory",
        memory,
        "--cpus",
        cpus,
        "--pids-limit",
        pids_limit,
        "--read-only",
        "--tmpfs",
        "/tmp:size=512m",
        "--network",
        network,
        "-v",
        _volume(workspace.input_dir, "/workspace/input", "ro"),
        "-v",
        _volume(workspace.work_dir, "/workspace/work", "rw"),
        "-v",
        _volume(workspace.output_dir, "/workspace/output", "rw"),
        "-v",
        _volume(workspace.logs_dir, "/workspace/logs", "rw"),
        "-v",
        _volume(workspace.task_file, "/workspace/task.json", "ro"),
        image,
        entrypoint,
    ]


def _volume(host: Path, container: str, mode: str) -> str:
    return f"{host}:{container}:{mode}"
