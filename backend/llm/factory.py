"""LLM client factory."""
import os
from threading import RLock
from typing import Any

from llm.base import BaseLLM
from llm.cloud_client import CloudClient
from llm.ollama_client import OllamaClient
from llm.provider_presets import CLOUD_VENDOR_PRESETS, build_provider_profile
from llm.runtime_config import get_llm_config_snapshot, get_provider_config
from settings_store import decode_key


_CLIENT_CACHE: dict[tuple[str, tuple[tuple[str, Any], ...]], BaseLLM] = {}
_CLIENT_CACHE_LOCK = RLock()


def resolve_provider_kind(provider: str | None = None) -> str:
    provider = provider or get_llm_config_snapshot()["provider"]
    if provider == "ollama":
        return "ollama"
    if provider in CLOUD_VENDOR_PRESETS or provider in {"openai", "custom"}:
        return "openai_compatible"
    raise ValueError(f"不支持的 LLM provider: {provider}")


def get_llm(provider: str | None = None) -> BaseLLM:
    kind = resolve_provider_kind(provider)
    if kind == "ollama":
        config = get_provider_config("ollama")
        return _cached_client("ollama", config, lambda: OllamaClient())
    if kind == "openai_compatible":
        config = get_provider_config("openai")
        if not config.get("api_key") and config.get("api_key_ref"):
            config["api_key"] = decode_key(config["api_key_ref"])
        if not config.get("api_key"):
            config["api_key"] = os.getenv("OPENAI_API_KEY", "")
        if provider:
            config["vendor"] = provider
        return _cached_client("openai_compatible", config, lambda: CloudClient(build_provider_profile(config)))
    raise ValueError(f"不支持的 LLM provider 类型: {kind}")


def _cached_client(kind: str, config: dict[str, Any], factory):
    key = (kind, _freeze_config(config))
    with _CLIENT_CACHE_LOCK:
        client = _CLIENT_CACHE.get(key)
        if client is None:
            client = factory()
            _CLIENT_CACHE[key] = client
        return client


def _freeze_config(config: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((key, _freeze_value(value)) for key, value in config.items()))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _freeze_config(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def clear_llm_cache() -> None:
    with _CLIENT_CACHE_LOCK:
        _CLIENT_CACHE.clear()


__all__ = ["get_llm", "resolve_provider_kind", "clear_llm_cache"]
