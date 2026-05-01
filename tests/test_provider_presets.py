"""LLM provider preset tests."""
from llm.provider_presets import (
    CLOUD_VENDOR_PRESETS,
    build_provider_profile,
    extract_model_names,
    get_cloud_vendor_preset,
    normalize_models_url,
)


def test_provider_presets_include_openai_compatible_metadata():
    preset = get_cloud_vendor_preset("deepseek")

    assert preset["id"] == "deepseek"
    assert preset["api_format"] == "openai_compatible"
    assert preset["base_url"] == "https://api.deepseek.com/v1"
    assert "model_placeholder" in preset


def test_unknown_provider_falls_back_to_custom():
    preset = get_cloud_vendor_preset("missing")

    assert preset == CLOUD_VENDOR_PRESETS["custom"]


def test_normalize_models_url_handles_openai_compatible_urls():
    assert normalize_models_url("https://api.openai.com/v1") == "https://api.openai.com/v1/models"
    assert normalize_models_url("https://proxy.example.com/v1/models") == "https://proxy.example.com/v1/models"
    assert normalize_models_url("") == "https://api.openai.com/v1/models"


def test_extract_model_names_supports_common_provider_payloads():
    assert extract_model_names({"data": [{"id": "gpt-4o-mini"}, {"name": "deepseek-chat"}]}) == [
        "gpt-4o-mini",
        "deepseek-chat",
    ]
    assert extract_model_names({"models": [{"model": "qwen-plus"}]}) == ["qwen-plus"]
    assert extract_model_names(["glm-4-plus"]) == ["glm-4-plus"]


def test_build_provider_profile_merges_runtime_config_with_preset_metadata():
    profile = build_provider_profile(
        {"vendor": "qwen", "api_key": "key", "base_url": "", "model": ""}
    )

    assert profile.vendor == "qwen"
    assert profile.label == "通义千问"
    assert profile.api_format == "openai_compatible"
    assert profile.api_key == "key"
    assert profile.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert profile.model == "qwen-plus"
