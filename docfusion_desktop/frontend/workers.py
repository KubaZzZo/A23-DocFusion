"""Qt workers for running API calls without blocking the interface."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(object)
    finished = Signal()


class ApiRunnable(QRunnable):
    def __init__(self, task: Callable[[], object]):
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.task())
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class ProgressApiRunnable(QRunnable):
    def __init__(self, task: Callable[[Callable[[object], None]], object]):
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.task(self.signals.progress.emit))
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()
