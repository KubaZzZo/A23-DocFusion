"""LLM统一接口"""
from abc import ABC, abstractmethod
from llm.cache import get_cached, set_cached
from llm.json_utils import parse_json_response, strip_json_code_fence
from logger import get_logger

log = get_logger("llm.base")


class BaseLLM(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        """发送消息并获取回复"""
        pass

    async def extract_json(self, prompt: str, text: str) -> dict:
        """从文本中提取结构化JSON"""
        cached = get_cached(prompt, text)
        if cached and not cached.get("parse_error"):
            log.info("命中缓存，跳过LLM调用")
            return cached

        messages = [
            {"role": "system", "content": "你是一个信息提取助手，请严格按JSON格式输出结果，不要输出其他内容。"},
            {"role": "user", "content": f"{prompt}\n\n文本内容：\n{text}"},
        ]
        result = await self.chat(messages)
        parsed = parse_json_response(result)
        if not parsed.get("parse_error"):
            set_cached(prompt, text, parsed)
        return parsed
