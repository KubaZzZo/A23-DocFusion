"""LLM client factory."""
from llm.base import BaseLLM
from llm.cloud_client import CloudClient
from llm.ollama_client import OllamaClient
from llm.provider_presets import CLOUD_VENDOR_PRESETS, build_provider_profile
from config import LLM_CONFIG


def resolve_provider_kind(provider: str | None = None) -> str:
    provider = provider or LLM_CONFIG["provider"]
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
        config = dict(LLM_CONFIG["openai"])
        if provider:
            config["vendor"] = provider
        return CloudClient(build_provider_profile(config))
    raise ValueError(f"不支持的 LLM provider 类型: {kind}")


__all__ = ["get_llm", "resolve_provider_kind"]
