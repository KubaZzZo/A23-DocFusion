"""LLM统一接口"""
import json
from abc import ABC, abstractmethod
from llm.cache import get_cached, set_cached
from logger import get_logger

log = get_logger("llm.base")


def strip_json_code_fence(text: str) -> str:
    """Remove common markdown code fences from an LLM JSON response."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    if "\n" in cleaned:
        first_line, rest = cleaned.split("\n", 1)
        if first_line.strip().lower() == "json":
            return rest.strip()

    if cleaned.lower().startswith("json"):
        return cleaned[4:].lstrip()
    return cleaned


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
        try:
            cleaned = strip_json_code_fence(result)
            parsed = json.loads(cleaned)
            set_cached(prompt, text, parsed)
            return parsed
        except json.JSONDecodeError:
            return {"raw_response": result, "parse_error": True}
