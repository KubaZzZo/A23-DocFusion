import json

from server_toolkit.task_models import TaskPlan, validate_workspace_path


def test_task_plan_accepts_l2_steps_and_preserves_outputs():
    plan = TaskPlan.from_dict(
        {
            "level": "L2",
            "requires_agent": False,
            "inputs": ["input/report.docx"],
            "outputs": ["output/report.pdf"],
            "timeout_seconds": 180,
            "steps": [
                {
                    "id": "step_1",
                    "tool": "docfusion",
                    "command": "convert",
                    "args": {
                        "input": "input/report.docx",
                        "to": "pdf",
                        "output": "output/report.pdf",
                    },
                }
            ],
        }
    )

    assert plan.level == "L2"
    assert plan.steps[0].command == "convert"
    assert plan.outputs == ["output/report.pdf"]


def test_task_plan_rejects_agent_mismatch():
    try:
        TaskPlan.from_dict(
            {
                "level": "L3",
                "requires_agent": False,
                "inputs": [],
                "outputs": [],
                "timeout_seconds": 600,
                "steps": [],
            }
        )
    except ValueError as exc:
        assert "requires_agent" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_workspace_path_rejects_escape_paths():
    for value in ("../secret.txt", "/etc/passwd", "input/../../x.txt"):
        try:
            validate_workspace_path(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected {value!r} to be rejected")


def test_task_plan_loads_from_json_file(tmp_path):
    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps(
            {
                "level": "L1",
                "requires_agent": False,
                "inputs": ["input/a.txt"],
                "outputs": ["output/a.txt"],
                "timeout_seconds": 60,
                "steps": [],
            }
        ),
        encoding="utf-8",
    )

    plan = TaskPlan.from_json_file(task_file)

    assert plan.level == "L1"
    assert plan.timeout_seconds == 60
