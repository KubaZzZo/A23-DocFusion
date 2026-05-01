"""Shared helpers for running UI tasks in background threads."""
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from logger import get_logger

log = get_logger("ui.task_runner")


class TaskWorker(QThread):
    """Run a callable in a QThread and emit normalized success/error signals."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], object], error_prefix: str = ""):
        super().__init__()
        self._task = task
        self._error_prefix = error_prefix

    def run(self):
        try:
            self.succeeded.emit(self._task())
        except Exception as e:
            log.exception("%s failed", self._error_prefix or "UI background task")
            self.failed.emit(str(e))
