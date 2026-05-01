"""Main window LLM status presentation tests."""

from pathlib import Path

from ui.main_window import _llm_status_snapshot


def test_llm_status_snapshot_formats_ollama_runtime_config():
    config = {
        "provider": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5:7b"},
        "openai": {"vendor": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    }

    snapshot = _llm_status_snapshot(config)

    assert snapshot["provider"] == "ollama"
    assert snapshot["label"] == "Ollama"
    assert snapshot["model"] == "qwen2.5:7b"
    assert snapshot["url"] == "http://localhost:11434"
    assert "Ollama" in snapshot["summary"]
    assert "qwen2.5:7b" in snapshot["summary"]
    assert "http://localhost:11434" in snapshot["tooltip"]


def test_llm_status_snapshot_formats_cloud_vendor_runtime_config():
    config = {
        "provider": "openai",
        "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5:7b"},
        "openai": {"vendor": "deepseek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    }

    snapshot = _llm_status_snapshot(config)

    assert snapshot["provider"] == "openai"
    assert snapshot["label"] == "DeepSeek"
    assert snapshot["model"] == "deepseek-chat"
    assert snapshot["url"] == "https://api.deepseek.com/v1"
    assert "DeepSeek" in snapshot["summary"]
    assert "deepseek-chat" in snapshot["summary"]


def test_main_window_uses_shared_status_bar_module():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "from ui.main_status_bar import MainStatusBar, llm_status_snapshot" in source
    assert "self.status_bar_widget = MainStatusBar(self._open_settings, self._on_provider_changed)" in source
    assert "def _refresh_llm_status" in source


def test_main_window_keeps_top_level_menu_setup():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "self._init_menu()" in source
    assert "def _init_menu(self):" in source


def test_main_window_updates_status_bar_on_provider_change():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "def _on_provider_changed(self, provider):" in source
    assert "self.statusBar().showMessage(f\"当前 LLM 提供方: {provider}\")" in source


def test_main_window_has_no_dead_llm_change_entrypoint():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "def _on_llm_changed(self, index):" not in source
