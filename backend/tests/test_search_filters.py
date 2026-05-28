import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from db.database import DocumentDAO, EntityDAO
from db.models import configure_database, init_db, reset_database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "search-test-token")
    init_db()
    first = DocumentDAO.create("contract-a.docx", "docx", str(tmp_path / "contract-a.docx"))
    second = DocumentDAO.create("memo-b.docx", "docx", str(tmp_path / "memo-b.docx"))
    DocumentDAO.update_text(first.id, "星河科技采购合同，合同金额120万元，签订日期2026-03-15。")
    DocumentDAO.update_text(second.id, "蓝海贸易服务备忘录，预算80万元，签订日期2025-12-20。")
    EntityDAO.create_batch(
        first.id,
        [
            {"type": "organization", "value": "星河科技", "context": "星河科技采购合同", "confidence": 0.95},
            {"type": "amount", "value": "120万元", "context": "合同金额120万元", "confidence": 0.95},
            {"type": "date", "value": "2026-03-15", "context": "签订日期2026-03-15", "confidence": 0.95},
        ],
    )
    EntityDAO.create_batch(
        second.id,
        [
            {"type": "organization", "value": "蓝海贸易", "context": "蓝海贸易服务备忘录", "confidence": 0.95},
            {"type": "amount", "value": "80万元", "context": "预算80万元", "confidence": 0.95},
            {"type": "date", "value": "2025-12-20", "context": "签订日期2025-12-20", "confidence": 0.95},
        ],
    )
    try:
        yield TestClient(app)
    finally:
        reset_database()


def test_search_returns_full_text_documents_and_matching_entities(client):
    response = client.get(
        "/api/search",
        params={"keyword": "星河科技"},
        headers={"Authorization": "Bearer search-test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [doc["filename"] for doc in payload["documents"]] == ["contract-a.docx"]
    assert [entity["value"] for entity in payload["entities"]] == ["星河科技"]


def test_entities_can_filter_by_amount_keyword_and_date_range(client):
    amount_response = client.get(
        "/api/entities",
        params={"entity_type": "amount", "keyword": "120万元"},
        headers={"Authorization": "Bearer search-test-token"},
    )
    assert amount_response.status_code == 200
    assert [entity["value"] for entity in amount_response.json()] == ["120万元"]

    date_response = client.get(
        "/api/entities",
        params={"entity_type": "date", "date_from": "2026-01-01", "date_to": "2026-12-31"},
        headers={"Authorization": "Bearer search-test-token"},
    )
    assert date_response.status_code == 200
    assert [entity["value"] for entity in date_response.json()] == ["2026-03-15"]


def test_search_query_parameters_have_length_and_format_limits(client):
    headers = {"Authorization": "Bearer search-test-token"}
    long_keyword = "x" * 201

    assert client.get("/api/documents", params={"q": long_keyword}, headers=headers).status_code == 422
    assert client.get("/api/entities", params={"keyword": long_keyword}, headers=headers).status_code == 422
    assert client.get("/api/search", params={"keyword": long_keyword}, headers=headers).status_code == 422
    assert client.get(
        "/api/entities",
        params={"date_from": "not-a-date"},
        headers=headers,
    ).status_code == 422
