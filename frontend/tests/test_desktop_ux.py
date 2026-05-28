import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QApplication

from docfusion_page import DocFusionWindow


def make_window():
    app = QApplication.instance() or QApplication([])
    return DocFusionWindow()


def test_keyboard_shortcuts_are_registered_for_navigation_and_document_actions():
    window = make_window()
    try:
        shortcuts = {shortcut.key().toString() for shortcut in window.findChildren(QShortcut)}

        assert {"Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5"}.issubset(shortcuts)
        assert "Ctrl+U" in shortcuts
        assert "Ctrl+R" in shortcuts
    finally:
        window.close()


def test_documents_load_uses_current_page_and_limit(monkeypatch):
    window = make_window()
    calls = []

    def fake_documents(page=1, limit=100, q=None):
        calls.append({"page": page, "limit": limit, "q": q})
        return []

    def run_immediately(label, task, on_success):
        on_success(task())

    monkeypatch.setattr(window.client, "documents", fake_documents)
    monkeypatch.setattr(window, "_run_api", run_immediately)

    try:
        window.document_page = 3
        window.document_page_size = 25
        window.document_keyword.setText("company")

        window.load_documents()

        assert calls == [{"page": 3, "limit": 25, "q": "company"}]
    finally:
        window.close()


def test_document_pagination_controls_update_page(monkeypatch):
    window = make_window()
    calls = []
    monkeypatch.setattr(window, "load_documents", lambda: calls.append(window.document_page))

    try:
        window.document_page = 1
        window.next_documents_page()
        window.previous_documents_page()

        assert calls == [2, 1]
        assert window.document_page == 1
    finally:
        window.close()


def test_busy_state_disables_action_buttons_until_finished():
    window = make_window()
    try:
        button = window.upload_button

        window._begin_action("loading")
        assert not button.isEnabled()
        assert not window.loading_indicator.isHidden()

        window._finish_action("loading")
        assert button.isEnabled()
        assert not window.loading_indicator.isVisible()
    finally:
        window.close()


def test_toast_displays_message_and_success_state(monkeypatch):
    window = make_window()
    single_shots = []
    monkeypatch.setattr("docfusion_page.QTimer.singleShot", lambda ms, callback: single_shots.append((ms, callback)))

    try:
        window.show_toast("done", success=True)

        assert window.toast_label.text() == "done"
        assert not window.toast_label.isHidden()
        assert single_shots and single_shots[0][0] == 3000
    finally:
        window.close()


def test_statistics_drive_pipeline_progress_from_api_data():
    window = make_window()
    try:
        window._on_statistics({"documents": 10, "parsed_documents": 5, "entities": 8, "templates": 1, "articles": 2})

        assert window.pipeline_bars["upload"].value() == 100
        assert window.pipeline_bars["parse"].value() == 50
        assert window.pipeline_bars["extract"].value() == 100
        assert window.pipeline_bars["template"].value() == 100
    finally:
        window.close()


def test_entity_graph_renders_readable_network_summary():
    window = make_window()
    try:
        window._on_entity_graph(
            {
                "nodes": [
                    {"id": "doc:1", "kind": "document", "label": "contract.docx"},
                    {"id": "entity:Acme", "kind": "entity", "label": "Acme"},
                ],
                "edges": [{"source": "doc:1", "target": "entity:Acme", "label": "mentions"}],
            }
        )

        text = window.entity_graph_view.toPlainText()
        assert "Nodes: 2" in text
        assert "Edges: 1" in text
        assert "contract.docx -> Acme" in text
    finally:
        window.close()


def test_demo_mode_loads_data_and_refreshes_competition_views(monkeypatch):
    window = make_window()
    calls = []

    def run_immediately(label, task, on_success):
        calls.append(label)
        on_success(task())

    monkeypatch.setattr(window.client, "load_demo_data", lambda: {"documents": 3, "entities": 14, "templates": 1})
    monkeypatch.setattr(window, "_run_api", run_immediately)
    monkeypatch.setattr(window, "refresh_all", lambda: calls.append("refresh_all"))
    monkeypatch.setattr(window, "load_cross_document_entities", lambda: calls.append("load_cross_document_entities"))
    monkeypatch.setattr(window, "load_entity_graph", lambda: calls.append("load_entity_graph"))

    try:
        window.run_demo_mode()

        assert calls == ["一键演示", "refresh_all", "load_cross_document_entities", "load_entity_graph"]
    finally:
        window.close()
