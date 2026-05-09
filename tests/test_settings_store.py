"""Settings storage tests independent of PyQt widgets."""
import shutil
import inspect
import sys
from pathlib import Path

import pytest

from settings_store import (
    apply_settings,
    decode_key,
    encode_key,
    load_settings,
    save_settings,
)

TMP_DIR = Path(__file__).parent / ".tmp_settings_store"


def test_settings_store_round_trips_encoded_api_key():
    if sys.platform != "win32":
        pytest.skip("DPAPI secure storage is Windows-only")
    TMP_DIR.mkdir(exist_ok=True)
    settings_path = TMP_DIR / "settings.json"
    settings = {
        "provider": "openai",
        "openai_key": encode_key("secret-key"),
        "openai_url": "https://api.example.com/v1",
        "openai_model": "demo-model",
    }

    save_settings(settings, settings_path)
    loaded = load_settings(settings_path)

    assert loaded["provider"] == "openai"
    assert loaded["openai_key"].startswith("dpapi:")
    assert "secret-key" not in loaded["openai_key"]
    assert decode_key(loaded["openai_key"]) == "secret-key"
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def test_decode_key_preserves_legacy_base64_values():
    assert decode_key("bGVnYWN5LWtleQ==") == "legacy-key"


def test_decode_key_rejects_legacy_plaintext_values():
    assert decode_key("plain-secret-key") == ""


def test_apply_settings_updates_runtime_config_without_ui_imports():
    if sys.platform != "win32":
        pytest.skip("DPAPI secure storage is Windows-only")
    runtime_config = {
        "provider": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5:7b"},
        "openai": {"vendor": "openai", "api_key": "", "api_key_ref": "", "base_url": "", "model": ""},
    }

    apply_settings(
        {
            "provider": "openai",
            "ollama_url": "http://127.0.0.1:11434",
            "ollama_model": "qwen3:8b",
            "openai_vendor": "deepseek",
            "openai_key": encode_key("cloud-key"),
            "openai_url": "https://api.deepseek.com/v1",
            "openai_model": "deepseek-chat",
        },
        runtime_config,
    )

    assert runtime_config["provider"] == "openai"
    assert runtime_config["ollama"]["model"] == "qwen3:8b"
    assert runtime_config["openai"]["vendor"] == "deepseek"
    assert runtime_config["openai"]["api_key"] == ""
    assert runtime_config["openai"]["api_key_ref"].startswith("dpapi:")
    assert runtime_config["openai"]["model"] == "deepseek-chat"


def test_apply_settings_default_runtime_config_is_none():
    assert inspect.signature(apply_settings).parameters["runtime_config"].default is None
