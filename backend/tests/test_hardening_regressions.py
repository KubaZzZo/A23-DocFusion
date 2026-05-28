import asyncio
import sys
import threading
from pathlib import Path

import pytest
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.doc_commander import DocCommander
from core.document_workflow import DocumentWorkflow
from core.entity_extractor import EntityExtractor
from core.semantic_matcher import SemanticMatcher
from core.template_filler import TemplateFiller
from core.template_workflow import TemplateWorkflow
from db.database import CrawledArticleDAO, DocumentDAO
from db.models import configure_database, init_db, reset_database
from llm import cache as llm_cache
import settings_store


def test_llm_memory_cache_is_protected_by_lock():
    assert isinstance(llm_cache._memory_cache_lock, threading.RLock().__class__)


@pytest.mark.asyncio
async def test_entity_verification_context_includes_late_entity_context():
    calls = []

    class FakeLLM:
        async def extract_json(self, prompt, text):
            calls.append(text)
            return {"entities": [{"type": "amount", "value": "9999元", "confidence": 0.95, "verified": True}]}

    extractor = EntityExtractor()
    extractor.llm = FakeLLM()
    original = "开头" + ("无关内容" * 700) + "合同总金额为9999元，付款到期日为2026-06-01。"
    result = {"entities": [{"type": "amount", "value": "9999元", "context": "合同总金额为9999元", "confidence": 0.4}]}

    await extractor._verify_low_confidence(result, original)

    assert calls
    assert "合同总金额为9999元" in calls[0]


@pytest.mark.asyncio
async def test_semantic_matcher_prompt_contains_actual_fields_and_entities():
    captured = {}

    class FakeLLM:
        async def extract_json(self, prompt, user_input):
            captured["prompt"] = prompt
            return {"matches": [], "unmatched_fields": ["审批人"]}

    matcher = SemanticMatcher()
    matcher.llm = FakeLLM()

    await matcher.match([">审批人<"], [{"type": "custom", "value": ">张三<", "confidence": 0.7}])

    assert ">审批人<" in captured["prompt"]
    assert ">张三<" in captured["prompt"]
    assert "{fields}" not in captured["prompt"]
    assert "{entities}" not in captured["prompt"]


@pytest.mark.asyncio
async def test_template_filler_removes_output_when_fill_fails(tmp_path, monkeypatch):
    template = tmp_path / "template.docx"
    doc = Document()
    table = doc.add_table(rows=2, cols=1)
    table.cell(0, 0).text = "姓名"
    doc.save(template)

    filler = TemplateFiller()

    class FakeMatcher:
        async def match(self, fields, entities):
            return {"matches": [{"field": "姓名", "value": "张三"}], "unmatched_fields": []}

    def fail_fill(*args, **kwargs):
        raise RuntimeError("fill failed")

    filler.matcher = FakeMatcher()
    monkeypatch.setattr(filler, "_fill_docx", fail_fill)
    monkeypatch.setattr("core.template_filler.OUTPUT_DIR", tmp_path)

    with pytest.raises(RuntimeError):
        await filler.fill(str(template), [{"type": "person", "value": "张三"}])

    assert list(tmp_path.glob("*_filled_*.docx")) == []


@pytest.mark.asyncio
async def test_template_workflow_run_fill_task_works_inside_running_event_loop(monkeypatch):
    calls = []

    async def fake_do_fill(self, task_id, template_path, entities):
        calls.append((task_id, template_path, entities))

    monkeypatch.setattr(TemplateWorkflow, "do_fill", fake_do_fill)

    TemplateWorkflow().run_fill_task(1, "template.docx", [])

    assert calls == [(1, "template.docx", [])]


def test_doc_commander_uses_same_lock_for_same_file(tmp_path):
    one = DocCommander._lock_for_path(tmp_path / "a.docx")
    two = DocCommander._lock_for_path(tmp_path / "." / "a.docx")
    other = DocCommander._lock_for_path(tmp_path / "b.docx")

    assert one is two
    assert one is not other


def test_settings_store_has_non_windows_fallback(monkeypatch):
    monkeypatch.setattr(settings_store, "_dpapi_available", lambda: False)

    encoded = settings_store.encode_key("secret-key")

    assert encoded.startswith(settings_store.FALLBACK_KEY_PREFIX)
    assert settings_store.decode_key(encoded) == "secret-key"


def test_crawled_article_uses_model_default_timestamp(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    init_db()
    try:
        article = CrawledArticleDAO.create("t", "a", "s", "u", "2026-01-01", "content")
        assert article.crawled_at is not None
    finally:
        reset_database()


@pytest.mark.asyncio
async def test_document_command_reparses_text_after_successful_edit(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    init_db()
    try:
        workflow = DocumentWorkflow(upload_dir=tmp_path / "uploads")
        source = tmp_path / "source.docx"
        doc = Document()
        doc.add_paragraph("old text")
        doc.save(source)
        uploaded = workflow.upload_document("edit.docx", source.read_bytes())
        workflow.parse_document(uploaded["id"])

        async def fake_parse_command(self, command, doc_info):
            return {"action": "find_replace", "target": "all", "params": {"find": "old", "replace": "new"}}

        monkeypatch.setattr(DocCommander, "parse_command", fake_parse_command)
        result = await workflow.execute_command(uploaded["id"], "replace old with new")

        assert result["result"]["success"] is True
        stored = DocumentDAO.get_by_id(uploaded["id"])
        assert "new text" in stored.raw_text
        assert "old text" not in stored.raw_text
    finally:
        reset_database()
