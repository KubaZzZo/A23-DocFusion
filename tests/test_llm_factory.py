"""LLM client factory tests."""
import pytest

from llm.cloud_client import CloudClient
from llm.factory import get_llm, resolve_provider_kind
from llm.ollama_client import OllamaClient
from config import LLM_CONFIG


def test_resolve_provider_kind_maps_cloud_vendors_to_openai_compatible():
    assert resolve_provider_kind("openai") == "openai_compatible"
    assert resolve_provider_kind("deepseek") == "openai_compatible"
    assert resolve_provider_kind("custom") == "openai_compatible"


def test_resolve_provider_kind_maps_ollama():
    assert resolve_provider_kind("ollama") == "ollama"


def test_resolve_provider_kind_rejects_unknown_provider():
    with pytest.raises(ValueError):
        resolve_provider_kind("unknown")


def test_get_llm_returns_expected_client_types():
    assert isinstance(get_llm("ollama"), OllamaClient)
    assert isinstance(get_llm("openai"), CloudClient)
    assert isinstance(get_llm("deepseek"), CloudClient)


def test_get_llm_with_explicit_cloud_provider_does_not_mutate_runtime_config():
    original_vendor = LLM_CONFIG["openai"]["vendor"]

    client = get_llm("deepseek")

    assert isinstance(client, CloudClient)
    assert client.profile.vendor == "deepseek"
    assert LLM_CONFIG["openai"]["vendor"] == original_vendor
