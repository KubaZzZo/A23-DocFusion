"""Settings dialog cloud vendor preset tests."""
from llm.provider_health import ProviderHealthResult
from ui.settings_dialog import (
    CLOUD_VENDOR_PRESETS,
    _extract_model_names,
    _format_provider_health_message,
    _normalize_models_url,
    get_cloud_vendor_preset,
)


def test_known_vendor_presets_exist():
    for vendor in ["openai", "deepseek", "moonshot", "qwen", "zhipu", "claude_compatible", "custom"]:
        preset = get_cloud_vendor_preset(vendor)
        assert preset["id"] == vendor
        assert preset["label"]
        assert "base_url" in preset
        assert "model_placeholder" in preset


def test_unknown_vendor_falls_back_to_custom():
    preset = get_cloud_vendor_preset("unknown-vendor")

    assert preset["id"] == "custom"
    assert preset["base_url"] == CLOUD_VENDOR_PRESETS["custom"]["base_url"]


def test_normalize_models_url_appends_models_path():
    assert _normalize_models_url("https://api.openai.com/v1") == "https://api.openai.com/v1/models"
    assert _normalize_models_url("https://code.77code.fun/") == "https://code.77code.fun/models"
    assert _normalize_models_url("https://code.77code.fun/v1/models") == "https://code.77code.fun/v1/models"


def test_extract_model_names_accepts_nonstandard_payloads():
    assert _extract_model_names({"data": [{"id": "gpt-4o-mini"}, {"id": "claude-opus-4-6"}]}) == [
        "gpt-4o-mini",
        "claude-opus-4-6",
    ]
    assert _extract_model_names({"data": ["claude-opus-4-6", {"name": "deepseek-chat"}]}) == [
        "claude-opus-4-6",
        "deepseek-chat",
    ]
    assert _extract_model_names("ok") == []


def test_format_provider_health_message_with_models():
    result = ProviderHealthResult(True, "连接正常", "https://api.example.com/v1/models", ["m1", "m2"])

    assert _format_provider_health_message("测试供应商", result) == "测试供应商 连接正常\n可用模型: m1, m2"


def test_format_provider_health_message_without_models():
    result = ProviderHealthResult(True, "兼容接口已响应，但未返回 JSON", "https://api.example.com/v1/models", [])

    assert _format_provider_health_message("测试供应商", result) == "测试供应商 连接正常\n兼容接口已响应，但未返回 JSON"
