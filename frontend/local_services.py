"""Local workflow bridges for capabilities that are not exposed as API routes."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from project_paths import resolve_project_root

PROJECT_ROOT = resolve_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.document_workflow import DocumentWorkflow  # noqa: E402
from db.database import CrawledArticleDAO, EntityDAO  # noqa: E402
from db.models import init_db  # noqa: E402
from crawler.doc_generator import DocGenerator  # noqa: E402
from config import LLM_CONFIG  # noqa: E402
from llm.provider_health import ProviderHealthChecker  # noqa: E402
from llm.provider_presets import CLOUD_VENDOR_PRESETS, build_provider_profile, get_cloud_vendor_preset  # noqa: E402
from settings_store import decode_key, encode_key, load_settings, save_settings  # noqa: E402


SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"


def batch_extract_documents(paths: list[str], progress: Callable[[dict], None] | None = None) -> dict:
    init_db()
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
                def extraction_progress(event: dict, filename: str = path.name) -> None:
                    if progress:
                        message = event.get("message") or ""
                        progress(
                            {
                                "current": index,
                                "total": total,
                                "message": f"{filename}: {message}",
                                "stage": event.get("stage"),
                                "chunk_current": event.get("current"),
                                "chunk_total": event.get("total"),
                            }
                        )

                extracted = loop.run_until_complete(
                    workflow.extract_entities(uploaded["id"], force=True, progress=extraction_progress)
                )
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
    init_db()
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
    init_db()
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
    init_db()
    saved = CrawledArticleDAO.create_batch(articles) if articles else []
    return {"saved": len(saved), "articles": len(articles)}


def generate_crawled_documents(articles: list[dict]) -> dict:
    init_db()
    return DocGenerator.generate_all(articles)


def cloud_vendor_options() -> list[tuple[str, str]]:
    return [(vendor_id, preset["label"]) for vendor_id, preset in CLOUD_VENDOR_PRESETS.items()]


def load_llm_provider_settings() -> dict:
    settings = load_settings(SETTINGS_FILE)
    provider = settings.get("provider", LLM_CONFIG.get("provider", "ollama"))
    vendor = settings.get("openai_vendor", LLM_CONFIG["openai"].get("vendor", "openai"))
    preset = get_cloud_vendor_preset(vendor)
    encoded_key = settings.get("openai_key", LLM_CONFIG["openai"].get("api_key_ref", ""))
    return {
        "provider": provider,
        "ollama_url": settings.get("ollama_url", LLM_CONFIG["ollama"].get("base_url", "http://localhost:11434")),
        "ollama_model": settings.get("ollama_model", LLM_CONFIG["ollama"].get("model", "qwen2.5:7b")),
        "openai_vendor": vendor,
        "openai_vendor_label": preset.get("label", vendor),
        "openai_key": decode_key(encoded_key) if encoded_key else "",
        "openai_url": settings.get("openai_url", LLM_CONFIG["openai"].get("base_url", preset.get("base_url", ""))),
        "openai_proxy": settings.get("openai_proxy", LLM_CONFIG["openai"].get("proxy_url", "")),
        "openai_model": settings.get("openai_model", LLM_CONFIG["openai"].get("model", preset.get("model_placeholder", ""))),
    }


def save_llm_provider_settings(config: dict) -> dict:
    provider = config.get("provider") or "ollama"
    api_key = config.get("openai_key", "")
    LLM_CONFIG["provider"] = provider
    LLM_CONFIG["ollama"]["base_url"] = config.get("ollama_url") or "http://localhost:11434"
    LLM_CONFIG["ollama"]["model"] = config.get("ollama_model") or "qwen2.5:7b"
    LLM_CONFIG["openai"]["vendor"] = config.get("openai_vendor") or "openai"
    LLM_CONFIG["openai"]["api_key"] = ""
    LLM_CONFIG["openai"]["api_key_ref"] = encode_key(api_key) if api_key else LLM_CONFIG["openai"].get("api_key_ref", "")
    LLM_CONFIG["openai"]["base_url"] = config.get("openai_url") or "https://api.openai.com/v1"
    LLM_CONFIG["openai"]["proxy_url"] = config.get("openai_proxy", "")
    LLM_CONFIG["openai"]["model"] = config.get("openai_model") or "gpt-4o-mini"

    settings = {
        "provider": LLM_CONFIG["provider"],
        "ollama_url": LLM_CONFIG["ollama"]["base_url"],
        "ollama_model": LLM_CONFIG["ollama"]["model"],
        "openai_vendor": LLM_CONFIG["openai"]["vendor"],
        "openai_key": LLM_CONFIG["openai"].get("api_key_ref", ""),
        "openai_url": LLM_CONFIG["openai"]["base_url"],
        "openai_proxy": LLM_CONFIG["openai"].get("proxy_url", ""),
        "openai_model": LLM_CONFIG["openai"]["model"],
    }
    save_settings(settings, SETTINGS_FILE)
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
