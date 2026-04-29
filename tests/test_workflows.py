"""Workflow module tests for API route orchestration."""
import asyncio
import io
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook

from db.models import Base, engine
from db.database import DocumentDAO, EntityDAO, FillTaskDAO
from core.document_workflow import DocumentWorkflow, WorkflowValidationError
from core.template_workflow import TemplateWorkflow


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


def test_document_workflow_parses_uploaded_document():
    workflow = DocumentWorkflow(upload_dir=WORKFLOW_UPLOAD_DIR)
    uploaded = workflow.upload_document("parse.txt", "解析内容".encode("utf-8"))

    result = workflow.parse_document(uploaded["id"])

    assert result["doc_id"] == uploaded["id"]
    assert result["text_length"] == len("解析内容")
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
