import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from docx import Document

import docfusion_page
from api_client import ApiClientConfig, DocFusionApiClient, load_api_client_config, save_api_client_config
from docfusion_page import DocFusionWindow
from server_task_client import DEFAULT_SERVER_TASK_URL
from workers import ApiRunnable


def make_window():
    app = QApplication.instance() or QApplication([])
    return DocFusionWindow()


def test_desktop_defaults_use_loopback_services():
    assert DocFusionApiClient().base_url == "https://docx.zhuoruan.xyz/api"
    assert DEFAULT_SERVER_TASK_URL == "https://docx.zhuoruan.xyz/toolkit"


def test_api_client_config_round_trips_user_token(tmp_path):
    path = tmp_path / "api.json"

    save_api_client_config(ApiClientConfig(base_url="https://example.test/api", token="secret"), path)
    loaded = load_api_client_config(path)

    assert loaded.base_url == "https://example.test/api"
    assert loaded.token == "secret"
    assert DocFusionApiClient(loaded.base_url, token=loaded.token)._token() == "secret"


def test_server_task_widgets_are_not_rebuilt_by_dead_page():
    assert not hasattr(DocFusionWindow, "_server_tasks_page")


def test_generation_page_has_own_sidebar_entry():
    window = make_window()
    try:
        labels = [button.text() for button in window.nav_buttons]
        assert any("生成" in label for label in labels)
        assert window.stack.count() == 6
    finally:
        window.close()


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


def test_server_task_completed_shows_clear_banner():
    window = make_window()
    try:
        window._on_server_task_status(
            {"task_id": "task-1", "status": "completed", "output_files": ["output/generated.docx"]}
        )

        assert "任务已完成" in window.server_task_status_banner.text()
        assert "可下载结果" in window.server_task_status_banner.text()
        assert "output/generated.docx" in window.server_task_status_banner.text()
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


def test_recent_articles_render_compact_rows():
    window = make_window()
    try:
        window._on_articles(
            [
                {
                    "id": 1,
                    "title": "网络安全公司SentinelOne将裁员约8%，加大对AI等领域投资",
                    "source": "36氪",
                    "category": "科技",
                    "publish_date": "2026-05-29",
                },
                {"id": 2, "title": "ui remote store smoke", "source": "smoke", "category": "test"},
            ]
        )

        assert window.recent_articles_count.text() == "2 篇"
        first_row = window.recent_articles_list.itemAt(0).widget()
        assert first_row.maximumHeight() <= 96
    finally:
        window.close()


def test_store_crawled_uses_backend_api(monkeypatch):
    window = make_window()
    calls = []
    try:
        window.crawled_preview = [{"title": "article"}]
        monkeypatch.setattr(window.client, "store_articles", lambda articles: calls.append(articles) or {"saved": 1, "articles": 1})
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.store_selected_crawled_articles()

        assert calls == [[{"title": "article"}]]
        assert "1/1" in window.crawl_status.text()
    finally:
        window.close()


def test_fusion_page_uses_backend_api(monkeypatch):
    window = make_window()
    calls = []
    try:
        monkeypatch.setattr(window.client, "cross_document_entities", lambda: calls.append("fusion") or [])
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.load_cross_document_entities()

        assert calls == ["fusion"]
    finally:
        window.close()


def test_fusion_export_uses_backend_api(monkeypatch, tmp_path):
    window = make_window()
    calls = []
    target = tmp_path / "fusion.xlsx"
    try:
        window.fusion_rows = [{"type": "organization", "value": "DocFusion测试公司"}]
        monkeypatch.setattr(docfusion_page.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), "Excel (*.xlsx)"))
        monkeypatch.setattr(
            window.client,
            "export_fusion_report",
            lambda path, rows: calls.append((Path(path), rows)) or target,
        )
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.export_fusion_report()

        assert calls == [(target, window.fusion_rows)]
    finally:
        window.close()


def test_generation_task_submits_without_files_and_renders_stream(monkeypatch):
    window = make_window()
    calls = []
    downloaded = []
    try:
        window.generation_instruction.setPlainText("生成一份校园采购验收报告")
        generated = Path(docfusion_page.tempfile.gettempdir()) / "docfusion_test_generated.docx"
        document = Document()
        document.add_paragraph("采购验收报告")
        document.save(generated)

        class FakeClient:
            def submit_generation(self, instruction, output_format="docx"):
                calls.append((instruction, output_format))
                return {"task_id": "task-gen", "status": "running", "progress": {"description": "running"}}

            def task_status(self, task_id):
                return {"task_id": task_id, "status": "completed", "output_files": ["output/generated.docx"]}

            def task_logs(self, task_id):
                return {"events": [{"event": "agent_output", "line": "writing document"}]}

            def download_result(self, task_id, destination):
                downloaded.append((task_id, Path(destination)))
                target = Path(destination) / "generated.docx"
                target.write_bytes(generated.read_bytes())
                return target

        monkeypatch.setattr(window, "_server_task_client", lambda: FakeClient())
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.submit_generation_task()
        window.refresh_generation_task_status()

        assert calls == [("生成一份校园采购验收报告", "docx")]
        assert "writing document" in window.generation_status_view.toPlainText()
        assert window.latest_generation_task_id == "task-gen"
        assert downloaded and downloaded[0][0] == "task-gen"
        assert "采购验收报告" in window.generation_preview_editor.toPlainText()
    finally:
        window.close()


def test_generation_preview_can_save_and_download_edited_docx(monkeypatch, tmp_path):
    window = make_window()
    try:
        window.latest_generation_task_id = "task-gen"
        window.generation_preview_editor.setPlainText("第一段\n第二段")
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.save_generation_preview()

        assert window.edited_generation_path
        saved = Document(str(window.edited_generation_path))
        assert [p.text for p in saved.paragraphs] == ["第一段", "第二段"]

        exported = tmp_path / "final.docx"
        monkeypatch.setattr(docfusion_page.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(exported), "Word 文档 (*.docx)"))
        opened = []
        monkeypatch.setattr(docfusion_page.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)

        window.download_generation_result()

        assert exported.exists()
        assert [p.text for p in Document(str(exported)).paragraphs] == ["第一段", "第二段"]
        assert opened
    finally:
        window.close()


def test_generation_format_controls_output_and_text_save(monkeypatch, tmp_path):
    window = make_window()
    calls = []
    try:
        window.generation_format.setCurrentIndex(3)
        window.generation_instruction.setPlainText("generate release notes")
        window.generation_preview_editor.setPlainText("hello txt")
        window.latest_generation_task_id = "task-gen"
        window.generated_document_path = tmp_path / "generated.txt"

        class FakeClient:
            def submit_generation(self, instruction, output_format="docx"):
                calls.append((instruction, output_format))
                return {"task_id": "task-gen", "status": "completed", "output_files": ["output/generated.txt"]}

            def download_result(self, task_id, destination):
                target = Path(destination) / "generated.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("hello txt", encoding="utf-8")
                return target

        monkeypatch.setattr(window, "_server_task_client", lambda: FakeClient())
        monkeypatch.setattr(window, "_run_api", lambda label, task, on_success: on_success(task()))

        window.submit_generation_task()
        window.save_generation_preview()

        assert calls == [("generate release notes", "txt")]
        assert window.edited_generation_path
        assert window.edited_generation_path.suffix == ".txt"
        assert window.edited_generation_path.read_text(encoding="utf-8") == "hello txt"
        assert window.generation_download_button.text() == "下载 TXT"
    finally:
        window.close()


def test_remote_document_is_downloaded_before_server_task_submit(monkeypatch, tmp_path):
    window = make_window()
    try:
        local = tmp_path / "remote.md"
        local.write_bytes(b"# md")
        window.documents = [{"id": 9, "filename": "remote.md", "file_path": "/opt/docfusion-main-api/backend/data/uploads/remote.md"}]
        window.selected_doc_id = 9
        calls = []
        monkeypatch.setattr(window.client, "download_document", lambda doc_id, directory: calls.append((doc_id, directory)) or local)

        result = window._server_task_input_files()

        assert result == [local]
        assert calls and calls[0][0] == 9
        assert calls[0][1].name == "remote.md"
    finally:
        window.close()
