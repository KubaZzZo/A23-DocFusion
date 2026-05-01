"""UI task runner regression tests."""
from pathlib import Path


def test_task_runner_defines_shared_worker_contract():
    source = Path("ui/task_runner.py").read_text(encoding="utf-8")

    assert "class TaskWorker(QThread)" in source
    assert "succeeded = pyqtSignal(object)" in source
    assert "failed = pyqtSignal(str)" in source
    assert "def run(self):" in source
    assert "self._task()" in source
    assert "log.exception" in source


def test_doc_panel_uses_shared_task_worker_for_command_execution():
    source = Path("ui/doc_panel.py").read_text(encoding="utf-8")

    assert "from ui.task_runner import TaskWorker" in source
    assert "CommandWorker" not in source
    assert "self.worker = TaskWorker(" in source
    assert "self.worker.succeeded.connect(self._on_command_done)" in source
    assert "self.worker.failed.connect(self._on_command_error)" in source


def test_fill_panel_uses_shared_task_worker_for_template_matching():
    source = Path("ui/fill_panel.py").read_text(encoding="utf-8")

    assert "from ui.task_runner import TaskWorker" in source
    assert "MatchWorker" not in source
    assert "self.match_worker = TaskWorker(" in source
    assert "self.match_worker.succeeded.connect(self._on_match_done)" in source
    assert "self.match_worker.failed.connect(self._on_fill_error)" in source
