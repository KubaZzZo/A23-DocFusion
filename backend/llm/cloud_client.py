"""云端LLM客户端（兼容OpenAI API格式）"""
import json

import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient
from llm.base import BaseLLM
from llm.provider_presets import ProviderProfile, build_provider_profile
from config import LLM_CONFIG
from logger import get_logger

log = get_logger("llm.cloud")


class CloudClient(BaseLLM):
    def __init__(self, profile: ProviderProfile | None = None):
        self.profile = profile or build_provider_profile(LLM_CONFIG["openai"])
        http_client = None
        if self.profile.proxy_url:
            http_client = DefaultAsyncHttpxClient(proxy=self.profile.proxy_url, trust_env=True)
        self.client = AsyncOpenAI(
            api_key=self.profile.api_key,
            base_url=self.profile.base_url,
            http_client=http_client,
        )
        self.model = self.profile.model

    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        log.info(f"Cloud请求: vendor={self.profile.vendor}, model={self.model}, messages={len(messages)}条")
        if not self.client.api_key:
            msg = f"{self.profile.label} API Key 未配置，请在设置中填写"
            log.error(msg)
            raise ConnectionError(msg)
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            result = self._extract_text(resp)
            log.info(f"Cloud响应: {len(result)}字符")
            return result
        except Exception as e:
            fallback_result = await self._chat_via_raw_http(messages, temperature, e)
            if fallback_result is not None:
                log.info(f"Cloud兼容响应: {len(fallback_result)}字符")
                return fallback_result
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                msg = "API Key 无效或已过期，请在设置中检查"
            elif "429" in err_str:
                msg = "API 请求频率超限，请稍后重试"
            elif "timeout" in err_str.lower():
                msg = "云端API请求超时，请检查网络连接"
            elif "Connection" in err_str:
                msg = f"无法连接到 {self.profile.label} API服务 ({self.client.base_url})，请检查网络或Base URL设置"
            else:
                msg = f"云端API调用失败: {err_str}"
            log.error(msg)
            raise RuntimeError(msg)

    async def _chat_via_raw_http(
        self,
        messages: list[dict],
        temperature: float,
        original_error: Exception,
    ) -> str | None:
        """Fallback for OpenAI-compatible gateways that return raw SSE text."""
        err_str = str(original_error)
        should_try = any(
            marker in err_str
            for marker in (
                "Expecting value",
                "Unsupported content type",
                "text/event-stream",
                "api_format",
            )
        )
        if not should_try:
            return None

        base_url = str(self.profile.base_url).rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.profile.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        try:
            async with httpx.AsyncClient(timeout=120, trust_env=True) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
        except Exception:
            return None

        content_type = resp.headers.get("content-type", "")
        body = resp.text
        if "text/event-stream" in content_type or body.lstrip().startswith("data:"):
            return self._extract_sse_text(body)
        try:
            return self._extract_text(resp.json())
        except Exception:
            return body

    @staticmethod
    def _extract_text(resp) -> str:
        if isinstance(resp, str):
            sse_text = CloudClient._extract_sse_text(resp)
            return sse_text if sse_text is not None else resp

        if isinstance(resp, dict):
            choices = resp.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                            parts.append(str(item["text"]))
                    if parts:
                        return "\n".join(parts)
            output_text = resp.get("output_text")
            if isinstance(output_text, str):
                return output_text

        choices = getattr(resp, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(str(text))
                    elif isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                        parts.append(str(item["text"]))
                if parts:
                    return "\n".join(parts)

        output_text = getattr(resp, "output_text", None)
        if isinstance(output_text, str):
            return output_text

        raise TypeError(f"Unsupported cloud response type: {type(resp).__name__}")

    @staticmethod
    def _extract_sse_text(resp_text: str) -> str | None:
        cleaned = (resp_text or "").strip()
        if not cleaned.startswith("data:"):
            return None

        parts = []
        saw_payload = False
        for line in cleaned.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            saw_payload = True
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue

            for choice in chunk.get("choices", []) or []:
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    parts.append(content)
                    continue
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                            parts.append(str(item["text"]))

                message = choice.get("message") or {}
                message_content = message.get("content")
                if isinstance(message_content, str) and message_content:
                    parts.append(message_content)

        if parts:
            return "".join(parts)
        if saw_payload:
            raise ValueError("当前模型未返回正文内容，可能不适合聊天/信息抽取，请更换为通用聊天模型")
        return None
