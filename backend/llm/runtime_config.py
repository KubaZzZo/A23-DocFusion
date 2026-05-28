"""Thread-safe access helpers for the mutable runtime LLM configuration."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from config import LLM_CONFIG


_CONFIG_LOCK = RLock()


def get_llm_config_snapshot() -> dict[str, Any]:
    """Return an isolated copy of the current LLM runtime config."""
    with _CONFIG_LOCK:
        return deepcopy(LLM_CONFIG)


def get_provider_config(provider: str) -> dict[str, Any]:
    """Return an isolated copy of one provider section."""
    with _CONFIG_LOCK:
        return deepcopy(LLM_CONFIG[provider])


def update_llm_config(settings: dict[str, Any]) -> None:
    """Apply persisted/UI settings while holding the runtime config lock."""
    if not settings:
        return
    with _CONFIG_LOCK:
        if "provider" in settings:
            LLM_CONFIG["provider"] = settings["provider"]
        if "ollama_url" in settings:
            LLM_CONFIG["ollama"]["base_url"] = settings["ollama_url"]
        if "ollama_model" in settings:
            LLM_CONFIG["ollama"]["model"] = settings["ollama_model"]
        if "openai_key" in settings:
            LLM_CONFIG["openai"]["api_key"] = ""
            LLM_CONFIG["openai"]["api_key_ref"] = settings["openai_key"]
        if "openai_vendor" in settings:
            LLM_CONFIG["openai"]["vendor"] = settings["openai_vendor"]
        if "openai_url" in settings:
            LLM_CONFIG["openai"]["base_url"] = settings["openai_url"]
        if "openai_model" in settings:
            LLM_CONFIG["openai"]["model"] = settings["openai_model"]
        if "openai_proxy" in settings:
            LLM_CONFIG["openai"]["proxy_url"] = settings["openai_proxy"]
    try:
        from llm.factory import clear_llm_cache

        clear_llm_cache()
    except ImportError:
        pass
