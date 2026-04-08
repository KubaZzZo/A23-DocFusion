"""Ollama本地模型客户端"""
import httpx
from llm.base import BaseLLM
from config import LLM_CONFIG
from logger import get_logger

log = get_logger("llm.ollama")


class OllamaClient(BaseLLM):
    def __init__(self):
        cfg = LLM_CONFIG["ollama"]
        self.base_url = cfg["base_url"]
        self.model = cfg["model"]

    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        log.info(f"Ollama请求: model={self.model}, messages={len(messages)}条")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                resp.raise_for_status()
                result = resp.json()["message"]["content"]
                log.info(f"Ollama响应: {len(result)}字符")
                return result
        except httpx.ConnectError:
            msg = f"无法连接到Ollama服务 ({self.base_url})，请确认Ollama已启动"
            log.error(msg)
            raise ConnectionError(msg)
        except httpx.TimeoutException:
            msg = "Ollama请求超时，模型可能正在加载中，请稍后重试"
            log.error(msg)
            raise TimeoutError(msg)
        except httpx.HTTPStatusError as e:
            msg = f"Ollama请求失败 (HTTP {e.response.status_code})，请检查模型 {self.model} 是否已下载"
            log.error(msg)
            raise RuntimeError(msg)
