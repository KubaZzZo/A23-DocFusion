"""Local workflow bridges for capabilities that are not exposed as API routes."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from project_paths import resolve_project_root

PROJECT_ROOT = resolve_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SETTINGS_FILE = Path.home() / ".docfusion" / "settings.json"
DEFAULT_LLM_CONFIG = {
    "provider": "ollama",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",
    "openai_vendor": "openai",
    "openai_key": "",
    "openai_url": "https://api.openai.com/v1",
    "openai_proxy": "",
    "openai_model": "gpt-4o-mini",
}
FALLBACK_CLOUD_VENDORS = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model_placeholder": "gpt-4o-mini"},
    "deepseek": {"label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model_placeholder": "deepseek-chat"},
    "moonshot": {"label": "Moonshot", "base_url": "https://api.moonshot.cn/v1", "model_placeholder": "moonshot-v1-8k"},
    "qwen": {"label": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model_placeholder": "qwen-plus"},
    "zhipu": {"label": "智谱", "base_url": "https://open.bigmodel.cn/api/paas/v4/", "model_placeholder": "glm-4-plus"},
}


def _init_db():
    from db.models import init_db

    init_db()


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_settings(settings: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def _encode_key(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii") if value else ""


def _decode_key(value: str) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value.encode("ascii")).decode("utf-8")
    except Exception:
        return value


def batch_extract_documents(paths: list[str], progress: Callable[[dict], None] | None = None) -> dict:
    from core.document_workflow import DocumentWorkflow

    _init_db()
    loop = asyncio.new_event_loop()
    try:
        workflow = DocumentWorkflow()
        successes = []
        failures = []
        total_entities = 0
        total = len(paths)
        for index, raw_path in enumerate(paths, start=1):
            path = Path(raw_path)
            if progress:
                progress({"current": index, "total": total, "message": f"处理 {path.name}"})
            try:
                uploaded = workflow.upload_document(path.name, path.read_bytes())
                parsed = workflow.parse_document(uploaded["id"])
                extracted = loop.run_until_complete(workflow.extract_entities(uploaded["id"], force=True))
                count = extracted.get("entities_count", 0)
                total_entities += count
                successes.append(
                    {
                        "id": uploaded["id"],
                        "filename": uploaded["filename"],
                        "text_length": parsed.get("text_length", 0),
                        "entities_count": count,
                    }
                )
            except Exception as exc:
                failures.append({"filename": path.name, "error": str(exc)})
        return {"documents": successes, "failures": failures, "entities_count": total_entities}
    finally:
        loop.close()


def clear_and_reextract_document(doc_id: int) -> dict:
    from core.document_workflow import DocumentWorkflow
    from db.database import EntityDAO

    _init_db()
    loop = asyncio.new_event_loop()
    try:
        EntityDAO.delete_by_document(doc_id)
        workflow = DocumentWorkflow()
        result = loop.run_until_complete(workflow.extract_entities(doc_id, force=True))
        result["cleared"] = True
        return result
    finally:
        loop.close()


def cross_document_entities(min_documents: int = 2, limit: int = 100) -> list[dict]:
    from db.database import EntityDAO

    _init_db()
    return EntityDAO.get_cross_document_entities(min_documents=min_documents, limit=limit)


def export_fusion_report(path: str | Path, rows: list[dict]) -> Path:
    from openpyxl import Workbook

    target = Path(path)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "跨文档实体关联"
    sheet.append(["实体类型", "实体值", "关联文档数", "出现次数", "平均置信度", "关联文档"])
    for item in rows:
        avg_confidence = item.get("avg_confidence")
        sheet.append(
            [
                item.get("type", ""),
                item.get("value", ""),
                item.get("doc_count", ""),
                item.get("count", ""),
                round(avg_confidence, 4) if avg_confidence is not None else "",
                "、".join(item.get("documents") or []),
            ]
        )

    summary = workbook.create_sheet("融合统计")
    summary.append(["指标", "值"])
    summary.append(["跨文档重复实体数", len(rows)])
    summary.append(["涉及文档总数", len({doc for item in rows for doc in item.get("documents", [])})])
    summary.append(["报告生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    workbook.save(target)
    return target


def store_crawled_articles(articles: list[dict]) -> dict:
    from db.database import CrawledArticleDAO

    _init_db()
    saved = CrawledArticleDAO.create_batch(articles) if articles else []
    return {"saved": len(saved), "articles": len(articles)}


def generate_crawled_documents(articles: list[dict]) -> dict:
    from crawler.doc_generator import DocGenerator

    _init_db()
    return DocGenerator.generate_all(articles)


def cloud_vendor_options() -> list[tuple[str, str]]:
    try:
        from llm.provider_presets import CLOUD_VENDOR_PRESETS
    except Exception:
        CLOUD_VENDOR_PRESETS = FALLBACK_CLOUD_VENDORS
    return [(vendor_id, preset["label"]) for vendor_id, preset in CLOUD_VENDOR_PRESETS.items()]


def load_llm_provider_settings() -> dict:
    settings = {**DEFAULT_LLM_CONFIG, **_load_settings(SETTINGS_FILE)}
    provider = settings.get("provider", "ollama")
    vendor = settings.get("openai_vendor", "openai")
    preset = FALLBACK_CLOUD_VENDORS.get(vendor, FALLBACK_CLOUD_VENDORS["openai"])
    encoded_key = settings.get("openai_key", "")
    return {
        "provider": provider,
        "ollama_url": settings.get("ollama_url", DEFAULT_LLM_CONFIG["ollama_url"]),
        "ollama_model": settings.get("ollama_model", DEFAULT_LLM_CONFIG["ollama_model"]),
        "openai_vendor": vendor,
        "openai_vendor_label": preset.get("label", vendor),
        "openai_key": _decode_key(encoded_key) if encoded_key else "",
        "openai_url": settings.get("openai_url", preset.get("base_url", DEFAULT_LLM_CONFIG["openai_url"])),
        "openai_proxy": settings.get("openai_proxy", DEFAULT_LLM_CONFIG["openai_proxy"]),
        "openai_model": settings.get("openai_model", preset.get("model_placeholder", DEFAULT_LLM_CONFIG["openai_model"])),
    }


def save_llm_provider_settings(config: dict) -> dict:
    provider = config.get("provider") or "ollama"
    api_key = config.get("openai_key", "")
    settings = {
        "provider": provider,
        "ollama_url": config.get("ollama_url") or DEFAULT_LLM_CONFIG["ollama_url"],
        "ollama_model": config.get("ollama_model") or DEFAULT_LLM_CONFIG["ollama_model"],
        "openai_vendor": config.get("openai_vendor") or DEFAULT_LLM_CONFIG["openai_vendor"],
        "openai_key": _encode_key(api_key) if api_key else "",
        "openai_url": config.get("openai_url") or DEFAULT_LLM_CONFIG["openai_url"],
        "openai_proxy": config.get("openai_proxy", ""),
        "openai_model": config.get("openai_model") or DEFAULT_LLM_CONFIG["openai_model"],
    }
    _save_settings(settings, SETTINGS_FILE)
    return load_llm_provider_settings()


def test_llm_provider_settings(config: dict) -> dict:
    provider = config.get("provider") or "ollama"
    if provider == "ollama":
        import httpx

        base_url = config.get("ollama_url") or "http://localhost:11434"
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        response.raise_for_status()
        models = [item.get("name", "") for item in response.json().get("models", []) if item.get("name")]
        return {"ok": True, "provider": "ollama", "message": "Ollama 连接正常", "models": models[:10]}

    try:
        from llm.provider_health import ProviderHealthChecker
        from llm.provider_presets import build_provider_profile

        profile = build_provider_profile(
            {
                "vendor": config.get("openai_vendor") or "openai",
                "api_key": config.get("openai_key", ""),
                "base_url": config.get("openai_url") or "https://api.openai.com/v1",
                "proxy_url": config.get("openai_proxy", ""),
                "model": config.get("openai_model", ""),
            }
        )
        result = ProviderHealthChecker().check_openai_compatible(profile)
        return {
            "ok": result.ok,
            "provider": profile.label,
            "url": result.url,
            "message": result.message,
            "models": result.models[:10],
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": config.get("openai_vendor") or "openai",
            "url": config.get("openai_url") or "https://api.openai.com/v1",
            "message": f"Provider test unavailable in this desktop build: {exc}",
            "models": [],
        }
