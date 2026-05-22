from pathlib import Path

from server_toolkit.docker_runtime import build_docker_command
from server_toolkit.workspace import TaskWorkspace


def test_build_docker_command_for_l1_uses_no_network_and_readonly_input(tmp_path):
    workspace = TaskWorkspace(root=tmp_path / "task_1")
    command = build_docker_command("task_1", workspace, level="L1")

    assert command[:2] == ["docker", "run"]
    assert "--rm" in command
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "docfusion-worker:latest" in command
    assert "/entrypoint.sh" in command
    assert _volume(command, workspace.input_dir, "/workspace/input", "ro")
    assert _volume(command, workspace.task_file, "/workspace/task.json", "ro")


def test_build_docker_command_for_l3_uses_agent_image_and_llm_network(tmp_path):
    workspace = TaskWorkspace(root=tmp_path / "task_3")
    command = build_docker_command(
        "task_3",
        workspace,
        level="L3",
        api_key_env="TASK_API_KEY",
    )

    assert "docfusion-agent:latest" in command
    assert "/entrypoint-agent.sh" in command
    assert command[command.index("--network") + 1] == "docfusion-llm-only"
    assert "-e" in command
    assert "OPENAI_API_KEY=${TASK_API_KEY}" in command
    assert command[command.index("--memory") + 1] == "4g"
    assert command[command.index("--cpus") + 1] == "2"


def test_build_docker_command_rejects_l3_without_api_key_env(tmp_path):
    workspace = TaskWorkspace(root=tmp_path / "task_3")

    try:
        build_docker_command("task_3", workspace, level="L3")
    except ValueError as exc:
        assert "api_key_env" in str(exc)
    else:
        raise AssertionError("expected api_key_env error")


def _volume(command: list[str], host: Path, container: str, mode: str) -> bool:
    value = f"{host}:{container}:{mode}"
    return "-v" in command and value in command
