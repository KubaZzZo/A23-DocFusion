import sys
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from api.routes import _attachment_headers
from core.document_workflow import DocumentWorkflow
from db.database import DocumentDAO, DocumentVersionDAO, FillTaskDAO
from db.models import configure_database, init_db, reset_database


FORBIDDEN_PATH_KEYS = {"path", "file_path", "backup_path", "template_path", "result_path", "report_path"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "redaction-test-token")
    init_db()
    try:
        yield TestClient(app), tmp_path
    finally:
        reset_database()


def _assert_no_path_keys(value):
    if isinstance(value, dict):
        leaked = FORBIDDEN_PATH_KEYS.intersection(value)
        assert leaked == set()
        for child in value.values():
            _assert_no_path_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_path_keys(child)


def _docx_bytes(path: Path) -> bytes:
    doc = Document()
    doc.add_paragraph("first line")
    doc.save(path)
    return path.read_bytes()


def test_document_api_responses_do_not_expose_server_paths(client):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}

    upload = test_client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("redacted.docx", _docx_bytes(tmp_path / "source.docx"))},
    )
    assert upload.status_code == 200
    _assert_no_path_keys(upload.json())
    doc_id = upload.json()["id"]

    command = test_client.post(
        "/api/documents/command",
        headers=headers,
        json={"doc_id": doc_id, "command": "make the first paragraph bold"},
    )
    assert command.status_code == 200
    _assert_no_path_keys(command.json())

    documents = test_client.get("/api/documents", headers=headers)
    assert documents.status_code == 200
    _assert_no_path_keys(documents.json())

    versions = test_client.get(f"/api/documents/{doc_id}/versions", headers=headers)
    assert versions.status_code == 200
    _assert_no_path_keys(versions.json())


def test_batch_api_response_does_not_expose_report_path(client):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}
    payload = "Vendor: Acme\nAmount: 120万元\nDate: 2026-03-15".encode("utf-8")

    response = test_client.post(
        "/api/batch/process",
        headers=headers,
        files=[("files", ("sample.txt", payload, "text/plain"))],
    )

    assert response.status_code == 200
    body = response.json()
    _assert_no_path_keys(body)
    assert body["download_url"].startswith("/api/batch/reports/")


def test_document_download_rejects_paths_outside_upload_dir(client):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}
    secret = tmp_path / "secret.txt"
    secret.write_text("do not download", encoding="utf-8")
    doc = DocumentDAO.create("secret.txt", "txt", str(secret))

    response = test_client.get(f"/api/documents/{doc.id}/download", headers=headers)

    assert response.status_code == 404


def test_version_download_rejects_paths_outside_backup_dir(client):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}
    doc = DocumentDAO.create("versioned.docx", "docx", str(tmp_path / "missing.docx"))
    secret = tmp_path / "secret-version.docx"
    secret.write_text("do not download", encoding="utf-8")
    version = DocumentVersionDAO.create(doc.id, str(secret), "unsafe")

    response = test_client.get(f"/api/documents/{doc.id}/versions/{version.id}/download", headers=headers)

    assert response.status_code == 404


def test_fill_result_download_rejects_paths_outside_output_dir(client):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}
    secret = tmp_path / "secret-result.docx"
    secret.write_text("do not download", encoding="utf-8")
    task = FillTaskDAO.create(template_id=1)
    FillTaskDAO.update_status(task.id, "completed", result_path=str(secret), accuracy=1.0)

    response = test_client.get(f"/api/templates/fill/{task.id}/download", headers=headers)

    assert response.status_code == 404


def test_download_filename_is_sanitized_in_content_disposition(client, monkeypatch):
    test_client, tmp_path = client
    headers = {"Authorization": "Bearer redaction-test-token"}
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    stored = upload_dir / "stored.docx"
    stored.write_bytes(_docx_bytes(tmp_path / "source.docx"))
    monkeypatch.setattr("api.routes.UPLOAD_DIR", upload_dir)
    doc = DocumentDAO.create('evil"\r\nX-Injected: yes;.docx', "docx", str(stored))

    response = test_client.get(f"/api/documents/{doc.id}/download", headers=headers)

    assert response.status_code == 200
    content_disposition = response.headers["content-disposition"]
    assert "X-Injected" not in content_disposition
    assert "\r" not in content_disposition
    assert "\n" not in content_disposition
    assert ";" in content_disposition


def test_attachment_headers_escape_special_filename_characters():
    headers = _attachment_headers('报告";\r\nX-Bad: 1.xlsx')
    value = headers["Content-Disposition"]

    assert "\r" not in value
    assert "\n" not in value
    assert "X-Bad" not in value
    assert "filename*=" in value
