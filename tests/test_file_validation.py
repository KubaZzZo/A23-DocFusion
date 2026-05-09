"""Upload file signature validation tests."""
import shutil
from pathlib import Path

import pytest

from core.document_workflow import DocumentWorkflow, WorkflowValidationError

TMP_DIR = Path(__file__).parent / ".tmp_file_validation"


@pytest.fixture(autouse=True)
def clean_tmp_dir():
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(exist_ok=True)
    yield
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def test_document_upload_rejects_pdf_with_wrong_magic():
    workflow = DocumentWorkflow(upload_dir=TMP_DIR)

    with pytest.raises(WorkflowValidationError):
        workflow.upload_document("fake.pdf", b"not a pdf")


def test_document_upload_accepts_pdf_magic():
    workflow = DocumentWorkflow(upload_dir=TMP_DIR)

    uploaded = workflow.upload_document("ok.pdf", b"%PDF-1.7\nbody")

    assert uploaded["filename"] == "ok.pdf"


def test_document_upload_rejects_docx_with_wrong_magic():
    workflow = DocumentWorkflow(upload_dir=TMP_DIR)

    with pytest.raises(WorkflowValidationError):
        workflow.upload_document("fake.docx", b"not a zip")
