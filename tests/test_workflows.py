"""Workflow module tests for API route orchestration."""
import asyncio
import io
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook

from db.models import Base, engine
from db.database import DocumentDAO, EntityDAO, FillTaskDAO, CrawledArticleDAO
from core.document_workflow import DocumentWorkflow, WorkflowValidationError
from core.template_workflow import TemplateWorkflow
from core.entity_workflow import EntityWorkflow
from core.article_workflow import ArticleWorkflow
from core.statistics_workflow import StatisticsWorkflow


WORKFLOW_UPLOAD_DIR = Path(__file__).parent / ".tmp_workflow_uploads"


@pytest.fixture(autouse=True)
def setup_db_and_uploads():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(WORKFLOW_UPLOAD_DIR, ignore_errors=True)
    WORKFLOW_UPLOAD_DIR.mkdir(exist_ok=True)
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(WORKFLOW_UPLOAD_DIR, ignore_errors=True)


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["姓名", "电话"])
    sheet.append(["", ""])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_document_workflow_uploads_and_renames_duplicate_files():
    workflow = DocumentWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)

    first = workflow.upload_document("same.txt", b"first")
    second = workflow.upload_document("same.txt", b"second")

    assert first["filename"] == "same.txt"
    assert second["filename"] == "same.txt"
    assert DocumentDAO.count() == 2
    assert Path(DocumentDAO.get_by_id(first["id"]).file_path).name == "same.txt"
    assert Path(DocumentDAO.get_by_id(second["id"]).file_path).name != "same.txt"


def test_document_workflow_rejects_unsupported_upload_format():
    workflow = DocumentWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)

    with pytest.raises(WorkflowValidationError):
        workflow.upload_document("bad.xyz", b"data")


def test_document_workflow_cleans_uploaded_file_when_database_create_fails(monkeypatch):
    workflow = DocumentWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)

    def fail_create(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("core.document_workflow.DocumentDAO.create", fail_create)

    with pytest.raises(RuntimeError):
        workflow.upload_document("orphan.txt", b"orphan")

    assert not (WORKFLOW_UPLOAD_DIR / "orphan.txt").exists()


def test_document_workflow_parses_uploaded_document():
    workflow = DocumentWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)
    uploaded = workflow.upload_document("parse.txt", "解析内容".encode("utf-8"))

    result = workflow.parse_document(uploaded["id"], include_text=True)

    assert result["doc_id"] == uploaded["id"]
    assert result["text_length"] == len("解析内容")
    assert result["text"] == "解析内容"
    assert DocumentDAO.get_by_id(uploaded["id"]).raw_text == "解析内容"


def test_template_workflow_uploads_template_and_creates_fill_task():
    template_workflow = TemplateWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)
    document = DocumentDAO.create("doc.txt", "txt", "/tmp/doc.txt")
    EntityDAO.create_batch(document.id, [{"type": "person", "value": "张三", "confidence": 0.9}])

    template = asyncio.run(template_workflow.upload_template("template.xlsx", _xlsx_bytes()))
    task = template_workflow.create_fill_task(template["id"], [document.id])

    assert template["filename"] == "template.xlsx"
    assert "姓名" in template["fields"]
    assert task["status"] == "pending"
    assert FillTaskDAO.get_by_id(task["task_id"]) is not None
    assert task["entities"] == [{"type": "person", "value": "张三", "confidence": 0.9}]


def test_template_workflow_cleans_uploaded_file_when_analysis_fails(monkeypatch):
    template_workflow = TemplateWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)

    async def fail_analyze(self, file_path):
        raise RuntimeError("analysis failed")

    monkeypatch.setattr("core.template_workflow.TemplateFiller.analyze_template", fail_analyze)

    with pytest.raises(RuntimeError):
        asyncio.run(template_workflow.upload_template("bad_template.xlsx", _xlsx_bytes()))

    assert not (WORKFLOW_UPLOAD_DIR / "bad_template.xlsx").exists()


def test_template_workflow_fills_confirmed_map_to_output_file():
    template_workflow = TemplateWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)
    template = asyncio.run(template_workflow.upload_template("confirmed.xlsx", _xlsx_bytes()))
    fill_map = {"姓名": "张三"}

    result = template_workflow.fill_confirmed_map(template["path"], fill_map)

    assert result["success"] is True
    assert result["filled"] == 1
    assert result["total"] == 2
    assert Path(result["output_path"]).exists()


def test_entity_workflow_lists_filters_and_exports_entities():
    workflow = EntityWorkflow()
    doc1 = DocumentDAO.create("a.txt", "txt", "/tmp/a.txt")
    doc2 = DocumentDAO.create("b.txt", "txt", "/tmp/b.txt")
    EntityDAO.create_batch(doc1.id, [{"type": "person", "value": "张三", "context": "负责人张三", "confidence": 0.9}])
    EntityDAO.create_batch(doc2.id, [{"type": "phone", "value": "13800138000", "context": "电话", "confidence": 0.95}])

    assert [e["value"] for e in workflow.list_entities(doc_id=doc1.id)] == ["张三"]
    assert [e["value"] for e in workflow.list_entities(keyword="138")] == ["13800138000"]

    csv_export = workflow.export_entities("csv")
    assert csv_export.filename == "entities.csv"
    assert csv_export.media_type == "text/csv; charset=utf-8"
    assert "张三" in csv_export.content.decode("utf-8-sig")

    xlsx_export = workflow.export_entities("xlsx")
    assert xlsx_export.filename == "entities.xlsx"
    assert xlsx_export.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert xlsx_export.content.startswith(b"PK")


def test_article_workflow_lists_and_fetches_article_details():
    workflow = ArticleWorkflow()
    article = CrawledArticleDAO.create("标题", "作者", "来源", "http://example.com", "2026-05-01", "正文", "新闻")

    listed = workflow.list_articles()
    detail = workflow.get_article(article.id)

    assert listed[0]["title"] == "标题"
    assert "content" not in listed[0]
    assert detail["content"] == "正文"
    assert detail["url"] == "http://example.com"


def test_statistics_workflow_returns_system_counts():
    workflow = StatisticsWorkflow()
    doc = DocumentDAO.create("stats.txt", "txt", "/tmp/stats.txt")
    EntityDAO.create_batch(doc.id, [{"type": "organization", "value": "测试公司", "confidence": 0.8}])
    CrawledArticleDAO.create("标题", "作者", "来源", "http://example.com", "2026-05-01", "正文", "新闻")

    stats = workflow.get_statistics()

    assert stats["documents"] == 1
    assert stats["entities"] == 1
    assert stats["articles"] == 1
    assert stats["entity_types"] == {"organization": 1}
