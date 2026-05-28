import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import DocFusionApiClient
from docfusion_page import DocFusionWindow
from server_task_client import DEFAULT_SERVER_TASK_URL, load_server_task_config
from PySide6.QtWidgets import QApplication


def test_main_api_client_defaults_to_local_backend_for_desktop_development():
    assert DocFusionApiClient().base_url == "http://127.0.0.1:8000/api"


def test_server_task_client_defaults_to_loopback_proxy_target(tmp_path):
    assert DEFAULT_SERVER_TASK_URL == "http://127.0.0.1:8010"
    loaded = load_server_task_config(tmp_path / "missing.json")
    assert loaded.base_url == "http://127.0.0.1:8010"


def test_settings_page_exposes_backend_mode_selector():
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    try:
        modes = [window.backend_mode.itemData(index) for index in range(window.backend_mode.count())]
        assert modes == ["local", "remote"]
    finally:
        window.close()


def test_remote_main_api_rejects_plain_http(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    refresh_calls = []
    monkeypatch.setattr(window, "refresh_all", lambda: refresh_calls.append(True))
    try:
        window.backend_mode.setCurrentIndex(window.backend_mode.findData("remote"))
        window.base_url_input.setText("http://example.com/api")

        assert window.apply_api_url() is False
        assert window.client.base_url == "http://127.0.0.1:8000/api"
        assert refresh_calls == []
    finally:
        window.close()


def test_local_main_api_allows_plain_http(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    monkeypatch.setattr(window, "refresh_all", lambda: None)
    try:
        window.backend_mode.setCurrentIndex(window.backend_mode.findData("local"))
        window.base_url_input.setText("http://127.0.0.1:8000/api")

        assert window.apply_api_url() is True
        assert window.client.base_url == "http://127.0.0.1:8000/api"
    finally:
        window.close()


def test_remote_server_task_rejects_plain_http(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = DocFusionWindow()
    saved = []
    monkeypatch.setattr("docfusion_page.save_server_task_config", lambda config, path: saved.append(config))
    try:
        window.server_task_backend_mode.setCurrentIndex(window.server_task_backend_mode.findData("remote"))
        window.server_task_url_input.setText("http://example.com/toolkit")

        assert window.save_server_task_settings() is False
        assert saved == []
    finally:
        window.close()
