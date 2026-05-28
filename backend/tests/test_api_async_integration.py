import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from db.models import configure_database, init_db, reset_database


@pytest.fixture()
def isolated_api(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "async-api-test-token")
    monkeypatch.setattr("config.UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr("config.OUTPUT_DIR", tmp_path / "outputs")
    init_db()
    try:
        yield
    finally:
        reset_database()


@pytest.mark.asyncio
async def test_document_upload_parse_and_list_request_chain_uses_asgi_app(isolated_api):
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer async-api-test-token"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload = await client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("contract.txt", b"Company Acme\nAmount 1200000", "text/plain")},
        )
        assert upload.status_code == 200
        doc_id = upload.json()["id"]

        parsed = await client.post(f"/api/documents/parse/{doc_id}", headers=headers)
        assert parsed.status_code == 200
        assert parsed.json()["text_length"] > 0

        listed = await client.get("/api/documents", headers=headers, params={"page": 1, "limit": 1, "q": "Acme"})
        assert listed.status_code == 200
        docs = listed.json()
        assert len(docs) == 1
        assert docs[0]["id"] == doc_id
