import json
import time

from server_toolkit.task_queue import InMemoryTaskQueue
from server_toolkit.task_service import TaskService


def test_queue_submit_returns_before_task_finishes(tmp_path):
    service = TaskService(tmp_path / "tasks")
    queue = InMemoryTaskQueue(service, max_concurrent_tasks=1, task_queue_size=2)
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    submitted = queue.submit(
        _copy_plan(),
        [source],
        task_id="task_1",
    )

    status = service.get_status(submitted.task_id)
    assert status["status"] in {"queued", "running"}
    queue.wait_for_idle(timeout=5)
    assert service.get_status(submitted.task_id)["status"] == "completed"


def test_queue_rejects_when_capacity_is_full(tmp_path):
    service = TaskService(tmp_path / "tasks")
    queue = InMemoryTaskQueue(service, max_concurrent_tasks=0, task_queue_size=1)

    queue.submit(_copy_plan(), [], task_id="task_1")

    try:
        queue.submit(_copy_plan(), [], task_id="task_2")
    except RuntimeError as exc:
        assert "QUEUE_FULL" in str(exc)
    else:
        raise AssertionError("expected queue full error")


def test_queue_cancel_queued_task_marks_cancelled(tmp_path):
    service = TaskService(tmp_path / "tasks")
    queue = InMemoryTaskQueue(service, max_concurrent_tasks=0, task_queue_size=2)

    queue.submit(_copy_plan(), [], task_id="task_1")
    status = queue.cancel("task_1")

    assert status["status"] == "cancelled"


def _copy_plan() -> dict:
    return {
        "level": "L1",
        "requires_agent": False,
        "inputs": [],
        "outputs": [],
        "timeout_seconds": 60,
        "steps": [],
    }
