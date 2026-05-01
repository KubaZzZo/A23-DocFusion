"""云端LLM客户端（兼容OpenAI API格式）"""
from openai import AsyncOpenAI
from llm.base import BaseLLM
from llm.provider_presets import ProviderProfile, build_provider_profile
from config import LLM_CONFIG
from logger import get_logger

log = get_logger("llm.cloud")


class CloudClient(BaseLLM):
    def __init__(self, profile: ProviderProfile | None = None):
        self.profile = profile or build_provider_profile(LLM_CONFIG["openai"])
        self.client = AsyncOpenAI(
            api_key=self.profile.api_key,
            base_url=self.profile.base_url,
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
            result = resp.choices[0].message.content
            log.info(f"Cloud响应: {len(result)}字符")
            return result
        except Exception as e:
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
