import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.semantic_matcher import SemanticMatcher
from core.workflow_engine import GenerateSummaryStep, WorkflowContext, WorkflowRunner, WorkflowStep
from core.doc_commander import CODEX_DOC_COMMAND_PROMPT
from api.auth import get_api_token
from llm import cache as llm_cache
from llm.cloud_client import CloudClient
from llm.provider_presets import ProviderProfile


def test_llm_memory_cache_is_protected_by_lock():
    assert isinstance(llm_cache._memory_cache_lock, threading.RLock().__class__)


def test_api_token_can_be_loaded_from_configured_file(tmp_path, monkeypatch):
    configured = tmp_path / "api_token"
    configured.write_text("from-file", encoding="utf-8")
    default_token = tmp_path / "default_token"
    monkeypatch.delenv("DOCFUSION_API_TOKEN", raising=False)
    monkeypatch.setenv("DOCFUSION_API_TOKEN_FILE", str(configured))

    assert get_api_token(default_token) == "from-file"
    assert not default_token.exists()


def test_no_world_writable_chmod_in_backend_sources():
    backend_root = Path(__file__).resolve().parent
    offenders = []
    forbidden = "chmod(" + "0o666)"
    for source in backend_root.rglob("*.py"):
        if "__pycache__" in source.parts:
            continue
        if source.name == Path(__file__).name:
            continue
        if forbidden in source.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(source.relative_to(backend_root).as_posix())

    assert offenders == []


def test_codex_doc_command_prompt_formats_namespace_literal():
    prompt = CODEX_DOC_COMMAND_PROMPT.format(
        doc_path="example.docx",
        user_input="make the first paragraph bold",
        doc_info="smoke",
    )

    assert "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia" in prompt


def test_entity_golden_data_has_competition_coverage():
    golden_file = Path(__file__).resolve().parent / "tests" / "golden_data" / "entity_extraction_golden.json"
    import json

    cases = json.loads(golden_file.read_text(encoding="utf-8"))
    allowed_types = {"person", "organization", "date", "amount", "phone", "email", "address", "id_number"}
    seen_types = set()
    for case in cases:
        for entity in case["expected_entities"]:
            seen_types.add(entity["type"])

    assert len(cases) >= 30
    assert seen_types >= allowed_types
    assert "money" not in seen_types


def test_semantic_matcher_maps_procurement_fields_without_llm():
    entities = [
        {"type": "organization", "value": "金陵科技学院创新中心", "confidence": 0.95},
        {"type": "organization", "value": "北京智远科技有限公司", "confidence": 0.95},
        {"type": "amount", "value": "268,000元", "confidence": 0.95},
        {"type": "date", "value": "2024-05-12", "confidence": 0.95},
        {"type": "person", "value": "张伟", "confidence": 0.95},
        {"type": "phone", "value": "13800138000", "confidence": 0.95},
        {"type": "email", "value": "zhangwei@example.com", "confidence": 0.95},
        {"type": "address", "value": "北京市海淀区中关村大街1号", "confidence": 0.95},
        {"type": "id_number", "value": "913100001234567890", "confidence": 0.95},
    ]
    fields = ["甲方", "供应商", "合同金额", "签订日期", "联系人", "电话", "邮箱", "地址", "税号"]

    result = SemanticMatcher._match_local(fields, entities)
    matched = {match["field"]: match["value"] for match in result["matches"]}

    assert matched["甲方"] == "金陵科技学院创新中心"
    assert matched["供应商"] == "北京智远科技有限公司"
    assert matched["税号"] == "913100001234567890"
    assert result["unmatched_fields"] == []


@pytest.mark.asyncio
async def test_generate_summary_accepts_dict_cross_document_entries(monkeypatch, tmp_path):
    captured = {}

    class FakeCommander:
        async def execute_via_codex(self, output_path, instruction):
            captured["instruction"] = instruction
            Path(output_path).write_text("summary", encoding="utf-8")
            return {"success": True}

    monkeypatch.setattr("core.workflow_engine.DocCommander", lambda: FakeCommander())

    ctx = WorkflowContext()
    ctx.set("entities", [{"type": "organization", "value": "北京智远科技", "confidence": 0.9}])
    ctx.set(
        "cross_doc",
        [
            {
                "type": "organization",
                "value": "北京智远科技有限公司",
                "doc_count": 2,
                "total_occurrences": 3,
                "variants": ["北京智远科技", "北京智远科技有限公司"],
            }
        ],
    )

    result = await GenerateSummaryStep("测试报告").run(ctx)

    assert result["success"] is True
    assert "北京智远科技有限公司" in captured["instruction"]
    assert "variants" in captured["instruction"]


@pytest.mark.asyncio
async def test_generate_summary_creates_docx_target_before_codex(monkeypatch, tmp_path):
    class FakeCommander:
        async def execute_via_codex(self, output_path, instruction):
            assert Path(output_path).exists()
            assert Path(output_path).suffix == ".docx"
            return {"success": True}

    monkeypatch.setattr("core.workflow_engine.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("core.workflow_engine.DocCommander", lambda: FakeCommander())

    ctx = WorkflowContext()
    ctx.set("entities", [{"type": "amount", "value": "1,280,000", "confidence": 0.9}])
    result = await GenerateSummaryStep("smoke").run(ctx)

    assert result["success"] is True
    assert Path(ctx.get("report_path")).exists()


@pytest.mark.asyncio
async def test_generate_summary_accepts_existing_report_when_codex_status_is_false(monkeypatch, tmp_path):
    class FakeCommander:
        async def execute_via_codex(self, output_path, instruction):
            assert Path(output_path).exists()
            return {"success": False, "message": "Codex wrapper did not report success"}

    monkeypatch.setattr("core.workflow_engine.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("core.workflow_engine.DocCommander", lambda: FakeCommander())

    ctx = WorkflowContext()
    ctx.set("entities", [{"type": "amount", "value": "1,280,000", "confidence": 0.9}])
    result = await GenerateSummaryStep("smoke").run(ctx)

    assert result["success"] is True
    assert ctx.get("report_path")


@pytest.mark.asyncio
async def test_workflow_runner_step_logs_do_not_collide_with_log_signature():
    class NoopStep(WorkflowStep):
        async def run(self, ctx):
            ctx.set("ran", True)
            return {"ok": True}

    runner = WorkflowRunner("smoke")
    runner.add_step(NoopStep("noop"))

    ctx = await runner.run()

    assert ctx.get("ran") is True
    step_logs = [entry for entry in ctx.logs if entry["step"] == "step_start"]
    assert len(step_logs) == 1
    assert step_logs[0]["step_name"] == "noop"


@pytest.mark.asyncio
async def test_semantic_matcher_prompt_contains_actual_fields_and_entities():
    captured = {}

    class FakeLLM:
        async def extract_json(self, prompt, user_input):
            captured["prompt"] = prompt
            return {"matches": [], "unmatched_fields": ["审批人"]}

    matcher = SemanticMatcher()
    matcher.llm = FakeLLM()

    await matcher.match([">审批人"], [{"type": "custom", "value": ">张三<", "confidence": 0.7}])

    assert ">审批人" in captured["prompt"]
    assert ">张三<" in captured["prompt"]
    assert "{fields}" not in captured["prompt"]
    assert "{entities}" not in captured["prompt"]


@pytest.mark.asyncio
async def test_cloud_client_falls_back_to_sse_text(monkeypatch):
    class FakeCompletions:
        async def create(self, **kwargs):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        api_key = "sk-test"
        chat = FakeChat()

    class FakeResponse:
        headers = {"content-type": "text/event-stream"}
        text = (
            'data: {"choices":[{"delta":{"content":"{\\"entities\\":"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"[]}"}}]}\n\n'
            "data: [DONE]\n\n"
        )

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("llm.cloud_client.httpx.AsyncClient", FakeAsyncClient)

    profile = ProviderProfile(
        vendor="custom",
        label="Custom",
        api_format="openai_compatible",
        api_key="sk-test",
        base_url="https://example.test/v1",
        model="test-model",
        proxy_url="",
    )
    client = CloudClient(profile)
    client.client = FakeOpenAI()

    result = await client.chat([{"role": "user", "content": "extract"}])

    assert result == '{"entities":[]}'
