import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import docfusion_page
from api_client import DocFusionApiClient
from docfusion_page import DocFusionWindow
from server_task_client import DEFAULT_SERVER_TASK_URL


def make_window():
    app = QApplication.instance() or QApplication([])
    return DocFusionWindow()


def test_desktop_defaults_use_loopback_services():
    assert DocFusionApiClient().base_url == "https://docx.zhuoruan.xyz/api"
    assert DEFAULT_SERVER_TASK_URL == "https://docx.zhuoruan.xyz/toolkit"


def test_server_task_widgets_are_not_rebuilt_by_dead_page():
    assert not hasattr(DocFusionWindow, "_server_tasks_page")


def test_log_view_appends_incrementally_and_limits_blocks(monkeypatch):
    window = make_window()
    calls = []

    def fail_to_plain_text():
        calls.append(True)
        raise AssertionError("log() should not rebuild the full log text")

    monkeypatch.setattr(window.log_view, "toPlainText", fail_to_plain_text)
    try:
        assert window.log_view.maximumBlockCount() == 500
        for index in range(510):
            window.log(f"event-{index}")

        assert calls == []
        assert "event-509" in window.log_view.document().toPlainText()
        assert window.log_view.document().blockCount() <= 500
    finally:
        window.close()


def test_server_task_polling_stops_after_max_attempts(monkeypatch):
    scheduled: list[tuple[int, object]] = []

    class FakeTimer:
        @staticmethod
        def singleShot(delay, callback):
            scheduled.append((delay, callback))

    monkeypatch.setattr(docfusion_page, "QTimer", FakeTimer)
    window = make_window()
    scheduled.clear()
    window.server_task_max_polls = 2

    try:
        window._on_server_task_status({"task_id": "task-1", "status": "running"})
        window._on_server_task_status({"task_id": "task-1", "status": "running"})
        window._on_server_task_status({"task_id": "task-1", "status": "running"})

        assert len(scheduled) == 2
        assert "轮询已停止" in window.server_task_status_view.toPlainText()

        window._on_server_task_status({"task_id": "task-1", "status": "completed"})
        assert window.server_task_poll_count == 0
    finally:
        window.close()
