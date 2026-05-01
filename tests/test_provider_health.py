"""LLM provider health check tests."""
from types import SimpleNamespace

import pytest

from llm.provider_health import ProviderHealthChecker
from llm.provider_presets import build_provider_profile


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=None):
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            error = RuntimeError(f"HTTP {self.status_code}")
            error.response = SimpleNamespace(status_code=self.status_code)
            raise error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def test_provider_health_success_extracts_models():
    profile = build_provider_profile({"vendor": "deepseek", "api_key": "key", "base_url": "", "model": ""})
    checker = ProviderHealthChecker(http_get=lambda url, headers, timeout: FakeResponse({"data": [{"id": "m1"}]}))

    result = checker.check_openai_compatible(profile)

    assert result.ok is True
    assert result.models == ["m1"]
    assert result.message == "连接正常"
    assert result.url.endswith("/models")


def test_provider_health_reports_missing_api_key_without_network_call():
    called = {"value": False}
    profile = build_provider_profile({"vendor": "openai", "api_key": "", "base_url": "", "model": ""})

    def http_get(url, headers, timeout):
        called["value"] = True
        return FakeResponse()

    result = ProviderHealthChecker(http_get=http_get).check_openai_compatible(profile)

    assert result.ok is False
    assert "API Key" in result.message
    assert called["value"] is False


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("timeout"), "超时"),
        (ConnectionError("network"), "无法连接"),
        (RuntimeError("HTTP 401"), "认证失败"),
        (RuntimeError("HTTP 429"), "频率超限"),
    ],
)
def test_provider_health_classifies_common_failures(error, expected):
    profile = build_provider_profile({"vendor": "openai", "api_key": "key", "base_url": "", "model": ""})
    checker = ProviderHealthChecker(http_get=lambda url, headers, timeout: (_ for _ in ()).throw(error))

    result = checker.check_openai_compatible(profile)

    assert result.ok is False
    assert expected in result.message


def test_provider_health_handles_non_json_success():
    profile = build_provider_profile({"vendor": "openai", "api_key": "key", "base_url": "", "model": ""})
    checker = ProviderHealthChecker(
        http_get=lambda url, headers, timeout: FakeResponse(json_error=ValueError("not json"))
    )

    result = checker.check_openai_compatible(profile)

    assert result.ok is True
    assert result.models == []
    assert "未返回 JSON" in result.message
