import sys
from pathlib import Path

from docx import Document


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.document_workflow import DocumentWorkflow
from db.models import configure_database, init_db, reset_database


def _docx_bytes(path: Path) -> bytes:
    doc = Document()
    doc.add_paragraph("safe filename")
    doc.save(path)
    return path.read_bytes()


def test_document_upload_uses_sanitized_storage_filename(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    init_db()
    try:
        workflow = DocumentWorkflow(upload_dir=tmp_path / "uploads")
        uploaded = workflow.upload_document(r"..\..\CON?.docx", _docx_bytes(tmp_path / "source.docx"))

        assert uploaded["filename"] == "CON_file.docx"
        assert Path(uploaded["path"]).name == "CON_file.docx"
        assert Path(uploaded["path"]).is_file()
    finally:
        reset_database()
