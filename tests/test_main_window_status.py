"""Main window LLM status presentation tests."""

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


def test_main_window_top_bar_has_distinct_model_and_endpoint_labels():
    source = __import__("pathlib").Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "self.lbl_llm_model" in source
    assert "self.lbl_llm_endpoint" in source
    assert "self._refresh_llm_status" in source
