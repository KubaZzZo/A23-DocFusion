import json
import zipfile

from server_toolkit.workspace import (
    collect_results,
    create_task_workspace,
    write_task_plan,
)


def test_create_task_workspace_builds_expected_dirs_and_copies_inputs(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    workspace = create_task_workspace(tmp_path / "tasks", "task_1", [source])

    assert workspace.root == tmp_path / "tasks" / "task_1"
    assert (workspace.input_dir / "source.txt").read_text(encoding="utf-8") == "hello"
    assert workspace.work_dir.is_dir()
    assert workspace.output_dir.is_dir()
    assert workspace.logs_dir.is_dir()


def test_create_task_workspace_rejects_duplicate_input_names(tmp_path):
    first = tmp_path / "a" / "same.txt"
    second = tmp_path / "b" / "same.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")

    try:
        create_task_workspace(tmp_path / "tasks", "task_1", [first, second])
    except ValueError as exc:
        assert "duplicate input filename" in str(exc)
    else:
        raise AssertionError("expected duplicate filename error")


def test_write_task_plan_serializes_json(tmp_path):
    workspace = create_task_workspace(tmp_path / "tasks", "task_1", [])
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": [],
        "outputs": ["output/result.txt"],
        "timeout_seconds": 60,
        "steps": [],
    }

    task_file = write_task_plan(workspace, plan)

    assert task_file == workspace.task_file
    assert json.loads(task_file.read_text(encoding="utf-8"))["outputs"] == ["output/result.txt"]


def test_collect_results_returns_single_file(tmp_path):
    workspace = create_task_workspace(tmp_path / "tasks", "task_1", [])
    result = workspace.output_dir / "result.txt"
    result.write_text("done", encoding="utf-8")

    collected = collect_results(workspace)

    assert collected.kind == "file"
    assert collected.path == result


def test_collect_results_zips_multiple_files(tmp_path):
    workspace = create_task_workspace(tmp_path / "tasks", "task_1", [])
    (workspace.output_dir / "a.txt").write_text("a", encoding="utf-8")
    (workspace.output_dir / "b.txt").write_text("b", encoding="utf-8")

    collected = collect_results(workspace)

    assert collected.kind == "zip"
    with zipfile.ZipFile(collected.path) as archive:
        assert sorted(archive.namelist()) == ["a.txt", "b.txt"]
