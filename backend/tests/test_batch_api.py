import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from api.auth import get_api_token
from db.models import configure_database, reset_database, init_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "batch-test-token")
    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    monkeypatch.setattr("config.UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr("config.OUTPUT_DIR", tmp_path / "outputs")
    init_db()
    try:
        yield TestClient(app)
    finally:
        reset_database()


def test_batch_process_endpoint_returns_report_download(client):
    response = client.post(
        "/api/batch/process",
        headers={"Authorization": "Bearer batch-test-token"},
        files=[
            ("files", ("one.txt", b"one@example.com", "text/plain")),
            ("files", ("two.txt", b"13800138000", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["succeeded"] == 2
    assert payload["download_url"].startswith("/api/batch/reports/")

    download = client.get(payload["download_url"], headers={"Authorization": "Bearer batch-test-token"})
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert len(download.content) > 1000
