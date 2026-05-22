import json
from datetime import datetime, timedelta, timezone

from server_toolkit.task_service import TaskService


def test_task_service_submit_and_run_local_task(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    service = TaskService(tmp_path / "tasks")
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": ["input/source.txt"],
        "outputs": ["output/result.txt"],
        "timeout_seconds": 60,
        "steps": [
            {
                "id": "copy",
                "tool": "docfusion",
                "command": "copy",
                "args": {"input": "input/source.txt", "output": "output/result.txt"},
            }
        ],
    }

    task = service.submit(plan, [source], task_id="task_1")
    result = service.run_local(task.task_id)

    status = service.get_status(task.task_id)
    assert result.success is True
    assert status["status"] == "completed"
    assert status["output_files"] == ["output/result.txt"]
    assert (tmp_path / "tasks" / "task_1" / "output" / "result.txt").read_text(encoding="utf-8") == "hello"


def test_task_service_failed_task_records_error(tmp_path):
    service = TaskService(tmp_path / "tasks")
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": [],
        "outputs": ["output/missing.txt"],
        "timeout_seconds": 60,
        "steps": [],
    }

    task = service.submit(plan, [], task_id="task_1")
    service.run_local(task.task_id)

    status = service.get_status(task.task_id)
    assert status["status"] == "failed"
    assert "declared output missing" in status["error"]


def test_task_service_reads_structured_logs(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    service = TaskService(tmp_path / "tasks")
    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": ["input/source.txt"],
            "outputs": ["output/result.txt"],
            "timeout_seconds": 60,
            "steps": [
                {
                    "id": "copy",
                    "tool": "docfusion",
                    "command": "copy",
                    "args": {"input": "input/source.txt", "output": "output/result.txt"},
                }
            ],
        },
        [source],
        task_id="task_1",
    )
    service.run_local(task.task_id)

    events = service.get_logs(task.task_id)

    assert [event["event"] for event in events] == ["start", "step_started", "step_completed", "complete"]


def test_task_service_collects_download_result(tmp_path):
    service = TaskService(tmp_path / "tasks")
    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": ["output/result.txt"],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_1",
    )
    workspace = service.get_workspace(task.task_id)
    (workspace.output_dir / "result.txt").write_text("done", encoding="utf-8")

    result = service.collect_download(task.task_id)

    assert result.kind == "file"
    assert result.path.name == "result.txt"


def test_task_service_persists_status_json(tmp_path):
    service = TaskService(tmp_path / "tasks")
    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": [],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_1",
    )

    status_file = service.get_workspace(task.task_id).root / "status.json"
    assert json.loads(status_file.read_text(encoding="utf-8"))["status"] == "queued"


def test_task_service_lists_tasks_with_status_filter(tmp_path):
    service = TaskService(tmp_path / "tasks")
    service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": [],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_1",
    )

    tasks = service.list_tasks(status="queued")

    assert [task["task_id"] for task in tasks] == ["task_1"]


def test_task_service_cancel_queued_task(tmp_path):
    service = TaskService(tmp_path / "tasks")
    service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": [],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_1",
    )

    service.cancel_task("task_1")

    assert service.get_status("task_1")["status"] == "cancelled"


def test_task_service_records_metadata_and_progress(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    service = TaskService(tmp_path / "tasks")

    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": ["input/source.txt"],
            "outputs": ["output/result.txt"],
            "timeout_seconds": 60,
            "steps": [
                {
                    "id": "copy",
                    "tool": "docfusion",
                    "command": "copy",
                    "args": {"input": "input/source.txt", "output": "output/result.txt"},
                }
            ],
        },
        [source],
        task_id="task_1",
        priority="high",
        timeout_seconds=30,
    )

    queued = service.get_status(task.task_id)
    assert queued["priority"] == "high"
    assert queued["timeout_seconds"] == 30
    assert queued["input_files"] == ["source.txt"]
    assert queued["progress"] == {"current_step": 0, "total_steps": 1, "description": "queued"}

    service.run_local(task.task_id)
    completed = service.get_status(task.task_id)
    assert completed["progress"] == {"current_step": 1, "total_steps": 1, "description": "completed"}


def test_task_service_collects_specific_download_result(tmp_path):
    service = TaskService(tmp_path / "tasks")
    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": ["output/a.txt", "output/b.txt"],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_1",
    )
    workspace = service.get_workspace(task.task_id)
    (workspace.output_dir / "a.txt").write_text("a", encoding="utf-8")
    (workspace.output_dir / "b.txt").write_text("b", encoding="utf-8")

    result = service.collect_download(task.task_id, file_path="output/b.txt")

    assert result.kind == "file"
    assert result.path.name == "b.txt"


def test_task_service_cleanup_expired_tasks(tmp_path):
    service = TaskService(tmp_path / "tasks")
    task = service.submit(
        {
            "level": "L1",
            "requires_agent": False,
            "inputs": [],
            "outputs": [],
            "timeout_seconds": 60,
            "steps": [],
        },
        [],
        task_id="task_old",
    )
    workspace = service.get_workspace(task.task_id)
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    status = service.get_status(task.task_id)
    status.update({"status": "completed", "completed_at": old_time})
    service._write_status(workspace, status)

    removed = service.cleanup_expired_tasks()

    assert removed == ["task_old"]
    assert not workspace.root.exists()
