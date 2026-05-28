import asyncio
import sys
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from db.models import configure_database, reset_database, init_db
from core.document_workflow import DocumentWorkflow


@pytest.fixture()
def client(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "version-test-token")
    init_db()
    workflow = DocumentWorkflow(upload_dir=tmp_path / "uploads")
    doc_path = tmp_path / "source.docx"
    doc = Document()
    doc.add_paragraph("first line")
    doc.save(doc_path)
    uploaded = workflow.upload_document("versioned.docx", doc_path.read_bytes())
    workflow.parse_document(uploaded["id"])
    asyncio.run(workflow.execute_command(uploaded["id"], "make the first paragraph bold"))
    try:
        yield TestClient(app), uploaded["id"]
    finally:
        reset_database()


def test_document_version_api_lists_downloads_and_rolls_back(client):
    test_client, doc_id = client
    headers = {"Authorization": "Bearer version-test-token"}

    versions_response = test_client.get(f"/api/documents/{doc_id}/versions", headers=headers)
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1

    version_id = versions[0]["id"]
    download_response = test_client.get(f"/api/documents/{doc_id}/versions/{version_id}/download", headers=headers)
    assert download_response.status_code == 200
    assert len(download_response.content) > 1000

    rollback_response = test_client.post(f"/api/documents/{doc_id}/versions/{version_id}/rollback", headers=headers)
    assert rollback_response.status_code == 200
    assert rollback_response.json()["success"] is True
