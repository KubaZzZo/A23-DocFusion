"""Shared helpers for running UI tasks in background threads."""
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from logger import get_logger

log = get_logger("ui.task_runner")


def is_worker_running(worker: QThread | None) -> bool:
    """Return whether a worker is still running, tolerating deleted Qt objects."""

    if worker is None:
        return False

    try:
        return worker.isRunning()
    except RuntimeError:
        # The Python wrapper can outlive the underlying Qt object briefly
        # after deleteLater() runs. Treat that as "not running".
        return False


class TaskWorker(QThread):
    """Run a callable in a QThread and emit normalized success/error signals.

    Automatically calls deleteLater() after finishing so callers don't
    accumulate orphaned QThread objects.
    """

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], object], error_prefix: str = ""):
        super().__init__()
        self._task = task
        self._error_prefix = error_prefix
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.succeeded.emit(self._task())
        except Exception as e:
            log.exception("%s failed", self._error_prefix or "UI background task")
            self.failed.emit(str(e))


class ProgressTaskWorker(QThread):
    """Run a progress-reporting callable in a QThread.

    Automatically calls deleteLater() after finishing so callers don't
    accumulate orphaned QThread objects.
    """

    progress = pyqtSignal(object)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[Callable[[object], None]], object], error_prefix: str = ""):
        super().__init__()
        self._task = task
        self._error_prefix = error_prefix
        self.finished.connect(self.deleteLater)

    def _emit_progress(self, event: object):
        self.progress.emit(event)

    def run(self):
        try:
            self.succeeded.emit(self._task(self._emit_progress))
        except Exception as e:
            log.exception("%s failed", self._error_prefix or "UI progress task")
            self.failed.emit(str(e))
