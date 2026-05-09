"""FastAPI 璺敱娴嬭瘯"""
import pytest
import io
import os
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault("DOCFUSION_API_TOKEN", "test-api-token")

from api.auth import get_api_token
from db.models import Base, engine, init_db
from api.server import app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {get_api_token()}"}

TEST_DIR = Path(__file__).parent / "test_data"
TEST_DIR.mkdir(exist_ok=True)


def api_get(path: str, **kwargs):
    headers = {**AUTH_HEADERS, **kwargs.pop("headers", {})}
    return client.get(path, headers=headers, **kwargs)


def api_post(path: str, **kwargs):
    headers = {**AUTH_HEADERS, **kwargs.pop("headers", {})}
    return client.post(path, headers=headers, **kwargs)


def api_delete(path: str, **kwargs):
    headers = {**AUTH_HEADERS, **kwargs.pop("headers", {})}
    return client.delete(path, headers=headers, **kwargs)


@pytest.fixture(autouse=True)
def setup_db():
    """姣忎釜娴嬭瘯鍓嶉噸寤烘暟鎹簱"""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _make_txt_file(content: str = "娴嬭瘯鏂囨。鍐呭", filename: str = "test.txt"):
    """鍒涘缓涓€涓唴瀛樹腑鐨則xt鏂囦欢鐢ㄤ簬涓婁紶"""
    return ("file", (filename, io.BytesIO(content.encode("utf-8")), "text/plain"))


class TestHealthCheck:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_business_endpoints_require_bearer_token(self):
        resp = client.get("/api/documents")

        assert resp.status_code == 401

    def test_business_endpoints_reject_wrong_bearer_token(self):
        resp = client.get("/api/documents", headers={"Authorization": "Bearer wrong"})

        assert resp.status_code == 401

    def test_mutating_endpoint_rejects_untrusted_origin(self):
        resp = api_delete("/api/documents/1", headers={"Origin": "https://evil.example"})

        assert resp.status_code == 403

    def test_mutating_endpoint_rejects_untrusted_referer_without_origin(self):
        resp = api_delete("/api/documents/1", headers={"Referer": "https://evil.example/page"})

        assert resp.status_code == 403

    def test_mutating_endpoint_allows_localhost_origin(self):
        resp = api_delete("/api/documents/99999", headers={"Origin": "http://localhost:3000"})

        assert resp.status_code == 404

    def test_list_routes_expose_page_limit_parameters(self):
        routes_source = Path(__file__).parents[1] / "api" / "routes.py"
        source = routes_source.read_text(encoding="utf-8")

        assert "class PageParams" in source
        assert "async def list_documents(pagination: PageParams = Depends())" in source
        assert "async def list_entities(doc_id: int = None, keyword: str = None, pagination: PageParams = Depends())" in source
        assert "async def list_articles(pagination: PageParams = Depends())" in source


class TestDocumentAPI:
    def test_upload_document(self):
        resp = api_post("/api/documents/upload", files=[_make_txt_file()])
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["filename"] == "test.txt"

    def test_upload_unsupported_format(self):
        file = ("file", ("test.xyz", io.BytesIO(b"data"), "application/octet-stream"))
        resp = api_post("/api/documents/upload", files=[file])
        assert resp.status_code == 400

    def test_upload_rejects_oversized_document(self, monkeypatch):
        monkeypatch.setattr("api.routes.MAX_UPLOAD_SIZE", 4)
        resp = api_post("/api/documents/upload", files=[_make_txt_file("12345")])

        assert resp.status_code == 413

    def test_list_documents(self):
        api_post("/api/documents/upload", files=[_make_txt_file()])
        resp = api_get("/api/documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1
        assert docs[0]["filename"] == "test.txt"

    def test_list_documents_supports_pagination(self):
        for idx in range(3):
            api_post("/api/documents/upload", files=[_make_txt_file(f"content-{idx}", f"doc{idx}.txt")])

        resp = api_get("/api/documents", params={"page": 2, "limit": 1})

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_parse_document(self):
        # 涓婁紶
        upload_resp = api_post("/api/documents/upload", files=[_make_txt_file("杩欐槸瑙ｆ瀽娴嬭瘯鍐呭")])
        doc_id = upload_resp.json()["id"]
        # 瑙ｆ瀽
        resp = api_post(f"/api/documents/parse/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["text_length"] > 0

    def test_parse_nonexistent(self):
        resp = api_post("/api/documents/parse/99999")
        assert resp.status_code == 404

    def test_delete_document(self):
        upload_resp = api_post("/api/documents/upload", files=[_make_txt_file()])
        doc_id = upload_resp.json()["id"]
        resp = api_delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        docs = api_get("/api/documents").json()
        assert all(d["id"] != doc_id for d in docs)

    def test_delete_nonexistent(self):
        resp = api_delete("/api/documents/99999")
        assert resp.status_code == 404


class TestEntityAPI:
    def test_list_entities_empty(self):
        resp = api_get("/api/entities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_entities_with_data(self):
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": "Alice", "context": "owner Alice", "confidence": 0.9},
            {"type": "phone", "value": "13800138000", "context": "phone 13800138000", "confidence": 0.95},
        ])
        resp = api_get("/api/entities")
        assert resp.status_code == 200
        entities = resp.json()
        assert len(entities) == 2

    def test_list_entities_supports_pagination(self):
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": f"person-{idx}", "confidence": 0.9}
            for idx in range(3)
        ])

        resp = api_get("/api/entities", params={"page": 2, "limit": 1})

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_entities_by_keyword(self):
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": "Alice", "confidence": 0.9},
            {"type": "person", "value": "Bob", "confidence": 0.85},
        ])
        resp = api_get("/api/entities", params={"keyword": "Alice"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["value"] == "Alice"

    def test_filter_entities_by_doc(self):
        from db.database import DocumentDAO, EntityDAO
        doc1 = DocumentDAO.create("a.txt", "txt", "/tmp/a.txt")
        doc2 = DocumentDAO.create("b.txt", "txt", "/tmp/b.txt")
        EntityDAO.create_batch(doc1.id, [{"type": "person", "value": "A", "confidence": 0.9}])
        EntityDAO.create_batch(doc2.id, [{"type": "person", "value": "B", "confidence": 0.9}])
        resp = api_get("/api/entities", params={"doc_id": doc1.id})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["value"] == "A"

    def test_export_entities_csv(self):
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": "Alice", "context": "owner Alice", "confidence": 0.9},
        ])
        resp = api_get("/api/entities/export", params={"fmt": "csv"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.content.decode("utf-8-sig")
        assert "type,value,context,confidence" in text
        assert "person" in text
        assert "Alice" in text

    def test_export_entities_xlsx(self):
        from openpyxl import load_workbook
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "phone", "value": "13800138000", "context": "phone 13800138000", "confidence": 0.95},
        ])
        resp = api_get("/api/entities/export", params={"fmt": "xlsx"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        workbook = load_workbook(io.BytesIO(resp.content))
        sheet = workbook.active
        assert sheet["A1"].value == "id"
        assert sheet["B2"].value == "phone"
        assert sheet["C2"].value == "13800138000"


class TestTemplateAPI:
    def _make_xlsx(self):
        """鍒涘缓涓€涓畝鍗曠殑xlsx妯℃澘鏂囦欢"""
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "phone", "email"])
        ws.append(["", "", ""])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return ("file", ("template.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))

    def test_upload_template(self):
        resp = api_post("/api/templates/upload", files=[self._make_xlsx()])
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "fields" in data
        assert len(data["fields"]) > 0

    def test_upload_template_rejects_oversized_file(self, monkeypatch):
        monkeypatch.setattr("api.routes.MAX_UPLOAD_SIZE", 4)
        resp = api_post("/api/templates/upload", files=[self._make_xlsx()])

        assert resp.status_code == 413


class TestArticleAPI:
    def test_list_articles_empty(self):
        resp = api_get("/api/articles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_articles_with_data(self):
        from db.database import CrawledArticleDAO
        CrawledArticleDAO.create("Test News", "Reporter", "Source", "http://example.com",
                                  "2026-03-18", "News content", "hot")
        resp = api_get("/api/articles")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "Test News"

    def test_list_articles_supports_pagination(self):
        from db.database import CrawledArticleDAO
        for idx in range(3):
            CrawledArticleDAO.create(f"News {idx}", "Reporter", "Source", f"http://example.com/{idx}",
                                      "2026-03-18", "News content", "hot")

        resp = api_get("/api/articles", params={"page": 2, "limit": 1})

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_article_detail(self):
        from db.database import CrawledArticleDAO
        article = CrawledArticleDAO.create("Detail Test", "Author", "Source", "http://test.com",
                                            "2026-03-20", "Detail content", "tech")
        resp = api_get(f"/api/articles/{article.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail Test"
        assert data["content"] == "Detail content"

    def test_get_article_nonexistent(self):
        resp = api_get("/api/articles/99999")
        assert resp.status_code == 404


class TestStatisticsAPI:
    def test_statistics_empty(self):
        resp = api_get("/api/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == 0
        assert data["entities"] == 0
        assert data["templates"] == 0
        assert data["articles"] == 0

    def test_statistics_with_data(self):
        from db.database import DocumentDAO, EntityDAO
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": "Alice", "confidence": 0.9},
            {"type": "organization", "value": "Example Corp", "confidence": 0.85},
        ])
        resp = api_get("/api/statistics")
        data = resp.json()
        assert data["documents"] == 1
        assert data["entities"] == 2
        assert "person" in data["entity_types"]
        assert data["entity_types"]["person"] == 1

