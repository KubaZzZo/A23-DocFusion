"""In-memory background queue for server toolkit tasks."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any, Iterable, Protocol

from server_toolkit.runners import LocalRunner
from server_toolkit.task_service import SubmittedTask, TaskService


class TaskExecutor(Protocol):
    def run(self, task_id: str) -> object:
        ...


class InMemoryTaskQueue:
    def __init__(
        self,
        service: TaskService,
        max_concurrent_tasks: int = 1,
        task_queue_size: int = 20,
        executor: TaskExecutor | None = None,
    ):
        self.service = service
        self.executor = executor or LocalRunner(service)
        self.max_concurrent_tasks = max_concurrent_tasks
        self._queue: queue.Queue[str] = queue.Queue(maxsize=task_queue_size)
        self._workers: list[threading.Thread] = []
        self._active = 0
        self._lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()
        for index in range(max_concurrent_tasks):
            worker = threading.Thread(target=self._worker_loop, name=f"docfusion-task-worker-{index}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def submit(
        self,
        plan: dict[str, Any],
        input_files: Iterable[str | Path],
        *,
        task_id: str,
        priority: str = "normal",
        timeout_seconds: int | None = None,
    ) -> SubmittedTask:
        if self._queue.full():
            raise RuntimeError("QUEUE_FULL")
        submitted = self.service.submit(
            plan,
            input_files,
            task_id=task_id,
            priority=priority,
            timeout_seconds=timeout_seconds,
        )
        self._idle.clear()
        self._queue.put_nowait(submitted.task_id)
        return submitted

    def cancel(self, task_id: str) -> dict[str, Any]:
        return self.service.cancel_task(task_id)

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    def _worker_loop(self) -> None:
        while True:
            task_id = self._queue.get()
            try:
                status = self.service.get_status(task_id)
                if status.get("status") != "cancelled":
                    with self._lock:
                        self._active += 1
                    self.executor.run(task_id)
            finally:
                with self._lock:
                    if self._active > 0:
                        self._active -= 1
                    if self._queue.empty() and self._active == 0:
                        self._idle.set()
                self._queue.task_done()
