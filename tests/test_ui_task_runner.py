"""UI task runner regression tests."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QPushButton, QProgressBar, QApplication

from ui.task_runner import ProgressTaskWorker, TaskWorker

_APP = None


def _qt_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _wait_for_worker(worker: TaskWorker, timeout_ms: int = 3000):
    _qt_app()
    loop = QEventLoop()
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.finished.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait(timeout_ms)


def test_task_runner_defines_shared_worker_contract():
    source = Path("ui/task_runner.py").read_text(encoding="utf-8")

    assert "class TaskWorker(QThread)" in source
    assert "succeeded = pyqtSignal(object)" in source
    assert "failed = pyqtSignal(str)" in source
    assert "def run(self):" in source
    assert "self._task()" in source
    assert "log.exception" in source


def test_progress_task_runner_defines_shared_worker_contract():
    source = Path("ui/task_runner.py").read_text(encoding="utf-8")

    assert "class ProgressTaskWorker(QThread)" in source
    assert "progress = pyqtSignal(object)" in source
    assert "succeeded = pyqtSignal(object)" in source
    assert "failed = pyqtSignal(str)" in source
    assert "self._task(self._emit_progress)" in source


def test_task_worker_emits_succeeded_for_successful_task():
    received = []
    worker = TaskWorker(lambda: {"ok": True})
    worker.succeeded.connect(received.append)

    _wait_for_worker(worker)

    assert received == [{"ok": True}]


def test_task_worker_emits_failed_for_raised_exception():
    received = []

    def fail():
        raise RuntimeError("boom")

    worker = TaskWorker(fail)
    worker.failed.connect(received.append)

    _wait_for_worker(worker)

    assert received == ["boom"]


def test_progress_task_worker_emits_progress_and_succeeded_for_successful_task():
    progress_events = []
    results = []

    def task(progress):
        progress({"current": 1, "total": 2, "label": "a.txt"})
        progress({"current": 2, "total": 2, "label": "b.txt"})
        return {"ok": True}

    worker = ProgressTaskWorker(task)
    worker.progress.connect(progress_events.append)
    worker.succeeded.connect(results.append)

    _wait_for_worker(worker)

    assert progress_events == [
        {"current": 1, "total": 2, "label": "a.txt"},
        {"current": 2, "total": 2, "label": "b.txt"},
    ]
    assert results == [{"ok": True}]


def test_progress_task_worker_emits_failed_for_raised_exception():
    received = []

    def task(progress):
        progress({"current": 1})
        raise RuntimeError("progress boom")

    worker = ProgressTaskWorker(task)
    worker.failed.connect(received.append)

    _wait_for_worker(worker)

    assert received == ["progress boom"]


def test_ui_error_callback_can_restore_button_and_progress_state():
    _qt_app()
    button = QPushButton("执行中...")
    progress = QProgressBar()
    button.setEnabled(False)
    progress.setVisible(True)

    def on_error(msg: str):
        button.setEnabled(True)
        button.setText("执行")
        progress.setVisible(False)

    worker = TaskWorker(lambda: (_ for _ in ()).throw(RuntimeError("failed")))
    worker.failed.connect(on_error)

    _wait_for_worker(worker)

    assert button.isEnabled()
    assert button.text() == "执行"
    assert not progress.isVisible()


def test_doc_panel_uses_shared_task_worker_for_command_execution():
    source = Path("ui/doc_panel.py").read_text(encoding="utf-8")

    assert "from core.document_workflow import DocumentWorkflow" in source
    assert "safe_copy" not in source
    assert "from ui.task_runner import TaskWorker" in source
    assert "CommandWorker" not in source
    assert "self.worker = TaskWorker(" in source
    assert "self.worker.succeeded.connect(self._on_command_done)" in source
    assert "self.worker.failed.connect(self._on_command_error)" in source


def test_fill_panel_uses_shared_task_worker_for_template_matching():
    source = Path("ui/fill_panel.py").read_text(encoding="utf-8")

    assert "from ui.task_runner import TaskWorker" in source
    assert "safe_copy" not in source
    assert "TemplateDAO.create" not in source
    assert "MatchWorker" not in source
    assert "self.match_worker = TaskWorker(" in source
    assert "self.match_worker.succeeded.connect(self._on_match_done)" in source
    assert "self.match_worker.failed.connect(self._on_fill_error)" in source


def test_dashboard_panel_uses_shared_task_worker_for_entity_qa():
    source = Path("ui/dashboard_panel.py").read_text(encoding="utf-8")

    assert "from ui.task_runner import TaskWorker" in source
    assert "EntityQAWorker" not in source
    assert "self.qa_worker = TaskWorker(" in source
    assert "self.qa_worker.succeeded.connect(self._on_entity_answer)" in source
    assert "self.qa_worker.failed.connect(self._on_entity_qa_error)" in source


def test_extract_panel_uses_shared_task_worker_for_single_extract():
    source = Path("ui/extract_panel.py").read_text(encoding="utf-8")

    assert "from core.document_workflow import DocumentWorkflow" in source
    assert "safe_copy" not in source
    assert "class ExtractWorker" not in source
    assert "from ui.task_runner import ProgressTaskWorker, TaskWorker" in source
    assert "class BatchExtractWorker" not in source
    assert "self.batch_worker = ProgressTaskWorker(" in source
    assert "self.batch_worker.progress.connect(self._on_batch_progress_event)" in source
    assert "self.worker = TaskWorker(" in source
    assert "self.worker.succeeded.connect(self._on_extract_done)" in source
    assert "self.worker.failed.connect(self._on_extract_error)" in source


def test_crawler_panel_uses_shared_task_worker_for_document_generation():
    source = Path("ui/crawler_panel.py").read_text(encoding="utf-8")

    assert "from core.document_workflow import DocumentWorkflow" in source
    assert "file_path.write_text" not in source
    assert "DocumentDAO.create" not in source
    assert "from ui.task_runner import ProgressTaskWorker, TaskWorker" in source
    assert "class DocGenWorker" not in source
    assert "CrawlWorker" in source
    assert "class ImportWorker" not in source
    assert "self.import_worker = ProgressTaskWorker(" in source
    assert "self.import_worker.progress.connect(self._on_import_progress_event)" in source
    assert "self.gen_worker = TaskWorker(" in source
    assert "self.gen_worker.succeeded.connect(self._on_gen_done)" in source
    assert "self.gen_worker.failed.connect(self._on_gen_error)" in source
