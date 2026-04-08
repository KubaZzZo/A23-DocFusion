"""LLM工厂，根据配置返回对应客户端"""
from llm.base import BaseLLM
from llm.ollama_client import OllamaClient
from llm.cloud_client import CloudClient
from config import LLM_CONFIG


def get_llm(provider: str = None) -> BaseLLM:
    provider = provider or LLM_CONFIG["provider"]
    if provider == "ollama":
        return OllamaClient()
    else:
        return CloudClient()
