import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import docfusion_page
from docfusion_page import DocFusionWindow


def test_server_task_polling_stops_after_max_attempts(monkeypatch):
    app = QApplication.instance() or QApplication([])
    scheduled: list[tuple[int, object]] = []

    class FakeTimer:
        @staticmethod
        def singleShot(delay, callback):
            scheduled.append((delay, callback))

    monkeypatch.setattr(docfusion_page, "QTimer", FakeTimer)
    window = DocFusionWindow()
    scheduled.clear()
    window.server_task_max_polls = 2

    window._on_server_task_status({"task_id": "task-1", "status": "running"})
    window._on_server_task_status({"task_id": "task-1", "status": "running"})
    window._on_server_task_status({"task_id": "task-1", "status": "running"})

    assert len(scheduled) == 2
    assert "轮询已停止" in window.server_task_status_view.toPlainText()

    window._on_server_task_status({"task_id": "task-1", "status": "completed"})

    assert window.server_task_poll_count == 0
    window.close()
