"""Persistent settings helpers independent of UI widgets."""
import base64
import json
import os
from pathlib import Path

from config import BASE_DIR, LLM_CONFIG
from logger import get_logger

DEFAULT_SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
log = get_logger("settings_store")


def encode_key(key: str) -> str:
    """Encode API keys before writing settings to disk."""
    if not key:
        return ""
    return base64.b64encode(key.encode("utf-8")).decode("utf-8")


def decode_key(encoded: str) -> str:
    """Decode stored API keys, preserving old plaintext values."""
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return encoded


def load_settings(settings_file: Path | str = DEFAULT_SETTINGS_FILE) -> dict:
    """Load persisted settings from JSON."""
    path = Path(settings_file)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("加载设置文件失败，使用默认设置: %s", e)
    return {}


def save_settings(settings: dict, settings_file: Path | str = DEFAULT_SETTINGS_FILE):
    """Save persisted settings to JSON."""
    path = Path(settings_file)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def apply_settings(settings: dict, runtime_config: dict = LLM_CONFIG):
    """Apply persisted settings to the runtime LLM config dictionary."""
    if not settings:
        return
    if "provider" in settings:
        runtime_config["provider"] = settings["provider"]
    if "ollama_url" in settings:
        runtime_config["ollama"]["base_url"] = settings["ollama_url"]
    if "ollama_model" in settings:
        runtime_config["ollama"]["model"] = settings["ollama_model"]
    if "openai_key" in settings:
        runtime_config["openai"]["api_key"] = decode_key(settings["openai_key"])
    if "openai_vendor" in settings:
        runtime_config["openai"]["vendor"] = settings["openai_vendor"]
    if "openai_url" in settings:
        runtime_config["openai"]["base_url"] = settings["openai_url"]
    if "openai_model" in settings:
        runtime_config["openai"]["model"] = settings["openai_model"]


def apply_saved_settings(settings_file: Path | str = DEFAULT_SETTINGS_FILE, runtime_config: dict = LLM_CONFIG):
    """Load settings from disk and apply them to runtime config."""
    apply_settings(load_settings(settings_file), runtime_config)
