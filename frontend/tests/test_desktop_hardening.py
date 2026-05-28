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
from workers import ApiRunnable


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


def test_api_runnable_is_retained_until_finished(monkeypatch):
    started = []
    window = make_window()
    try:
        monkeypatch.setattr(window.pool, "start", lambda runnable: started.append(runnable))

        window._run_api("测试任务", lambda: {"ok": True}, lambda data: None)

        assert len(started) == 1
        runnable = started[0]
        assert isinstance(runnable, ApiRunnable)
        assert runnable in window._active_runnables

        runnable.signals.finished.emit()

        assert runnable not in window._active_runnables
    finally:
        window.close()


def test_export_write_uses_timestamp_fallback_on_permission_error(monkeypatch, tmp_path):
    target = tmp_path / "entities.csv"
    fallback = tmp_path / "entities_20260528_201900.csv"
    payload = b"name,value\n"
    writes = []

    def fake_write_bytes(self, data):
        writes.append(self)
        if self == target:
            raise PermissionError("locked")
        assert self == fallback
        assert data == payload
        return len(data)

    monkeypatch.setattr("api_client.datetime", type("FakeDatetime", (), {"now": staticmethod(lambda: type("FakeNow", (), {"strftime": lambda self, fmt: "20260528_201900"})())}))
    monkeypatch.setattr(Path, "write_bytes", fake_write_bytes)

    result = DocFusionApiClient()._write_payload_with_fallback(payload, target)

    assert result == fallback
    assert writes == [target, fallback]


def test_statistics_preview_uses_chinese_labels():
    window = make_window()
    try:
        preview = window._format_statistics_preview(
            {
                "documents": 12,
                "entities": 90,
                "templates": 0,
                "articles": 3,
                "entity_types": {"address": 20, "amount": 9, "custom": 34, "date": 1},
            }
        )

        assert "文档数量：12" in preview
        assert "实体类型分布：" in preview
        assert "地址：20" in preview
        assert '"documents"' not in preview
    finally:
        window.close()


def test_store_and_generate_crawled_updates_status(monkeypatch):
    calls = []
    window = make_window()
    try:
        monkeypatch.setattr(window, "load_articles", lambda: calls.append("articles"))
        monkeypatch.setattr(window, "load_documents", lambda: calls.append("documents"))
        monkeypatch.setattr(window, "load_statistics", lambda: calls.append("statistics"))

        window._after_store_crawled({"saved": 2, "articles": 3})
        assert "成功保存 2/3 篇文章" in window.crawl_status.text()
        assert calls == ["articles", "statistics"]

        calls.clear()
        window._after_generate_crawled_documents({"docx": ["a.docx", "b.docx"]})
        assert "生成 2 个文档" in window.crawl_status.text()
        assert calls == ["documents", "statistics"]
    finally:
        window.close()
