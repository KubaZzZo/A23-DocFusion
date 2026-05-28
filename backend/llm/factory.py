"""LLM client factory."""
import os

from llm.base import BaseLLM
from llm.cloud_client import CloudClient
from llm.ollama_client import OllamaClient
from llm.provider_presets import CLOUD_VENDOR_PRESETS, build_provider_profile
from llm.runtime_config import get_llm_config_snapshot, get_provider_config
from settings_store import decode_key


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
        return OllamaClient()
    if kind == "openai_compatible":
        config = get_provider_config("openai")
        if not config.get("api_key") and config.get("api_key_ref"):
            config["api_key"] = decode_key(config["api_key_ref"])
        if not config.get("api_key"):
            config["api_key"] = os.getenv("OPENAI_API_KEY", "")
        if provider:
            config["vendor"] = provider
        return CloudClient(build_provider_profile(config))
    raise ValueError(f"不支持的 LLM provider 类型: {kind}")


__all__ = ["get_llm", "resolve_provider_kind"]
