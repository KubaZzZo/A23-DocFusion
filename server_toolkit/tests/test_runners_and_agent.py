from server_toolkit.agent import build_agent_prompt, validate_l3_plan
from server_toolkit.runners import DockerRunner, LocalRunner
from server_toolkit.task_service import TaskService


def test_local_runner_executes_task(tmp_path):
    service = TaskService(tmp_path / "tasks")
    service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": ["output/result.txt"],
            "timeout_seconds": 60,
            "steps": [
                {
                    "id": "copy",
                    "tool": "docfusion",
                    "command": "copy",
                    "args": {"input": "work/source.txt", "output": "output/result.txt"},
                }
            ],
        },
        [],
        task_id="task_1",
    )
    workspace = service.get_workspace("task_1")
    (workspace.work_dir / "source.txt").write_text("hello", encoding="utf-8")

    result = LocalRunner(service).run("task_1")

    assert result.success is True


def test_docker_runner_dry_run_returns_command(tmp_path):
    service = TaskService(tmp_path / "tasks")
    service.submit(
        {"level": "L1", "requires_agent": False, "inputs": [], "outputs": [], "timeout_seconds": 60, "steps": []},
        [],
        task_id="task_1",
    )

    result = DockerRunner(service, dry_run=True).run("task_1")

    assert result.success is True
    assert result.command[:2] == ["docker", "run"]


def test_validate_l3_plan_requires_agent_flag():
    plan = {"level": "L3", "requires_agent": False}

    try:
        validate_l3_plan(plan)
    except ValueError as exc:
        assert "requires_agent" in str(exc)
    else:
        raise AssertionError("expected requires_agent validation")


def test_build_agent_prompt_mentions_workspace_and_docfusion():
    prompt = build_agent_prompt("Generate report")

    assert "/workspace/input" in prompt
    assert "docfusion" in prompt
    assert "Generate report" in prompt
