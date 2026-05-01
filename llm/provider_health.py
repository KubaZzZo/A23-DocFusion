"""Provider health checks for OpenAI-compatible LLM APIs."""
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from llm.provider_presets import ProviderProfile, extract_model_names, normalize_models_url


@dataclass(frozen=True)
class ProviderHealthResult:
    ok: bool
    message: str
    url: str
    models: list[str]


class ProviderHealthChecker:
    def __init__(self, http_get: Callable | None = None, timeout: int = 10):
        self.http_get = http_get or httpx.get
        self.timeout = timeout

    def check_openai_compatible(self, profile: ProviderProfile) -> ProviderHealthResult:
        url = normalize_models_url(profile.base_url)
        if not profile.api_key:
            return ProviderHealthResult(False, f"{profile.label} API Key 未配置", url, [])

        try:
            response = self.http_get(
                url,
                headers={"Authorization": f"Bearer {profile.api_key}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                return ProviderHealthResult(True, "兼容接口已响应，但未返回 JSON", url, [])

            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                error = payload["error"].get("message") or str(payload["error"])
                return ProviderHealthResult(False, error, url, [])

            models = extract_model_names(payload)
            return ProviderHealthResult(True, "连接正常", url, models)
        except Exception as e:
            return ProviderHealthResult(False, self._classify_error(e), url, [])

    @staticmethod
    def _classify_error(error: Exception) -> str:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        text = str(error)
        if status_code == 401 or "401" in text or "Unauthorized" in text:
            return "认证失败，请检查 API Key"
        if status_code == 429 or "429" in text:
            return "请求频率超限，请稍后重试"
        if isinstance(error, TimeoutError) or isinstance(error, httpx.TimeoutException) or "timeout" in text.lower():
            return "请求超时，请检查网络或稍后重试"
        if isinstance(error, ConnectionError) or isinstance(error, httpx.ConnectError):
            return "无法连接到 API 服务，请检查网络或 Base URL"
        return f"连接失败: {text}"


__all__ = ["ProviderHealthChecker", "ProviderHealthResult"]
