"""Crawler import workflow tests."""
from pathlib import Path

from db.database import DocumentDAO
from db.models import Base, engine
from ui import crawler_panel
from ui.crawler_panel import ImportWorker


class FakeExtractor:
    async def extract(self, content: str) -> dict:
        return {"entities": []}


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def teardown_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_import_worker_stores_crawled_article_as_real_file(monkeypatch):
    monkeypatch.setattr(crawler_panel, "EntityExtractor", FakeExtractor)
    article = {
        "title": "测试新闻标题",
        "author": "作者",
        "source": "来源",
        "url": "http://example.com/article",
        "publish_date": "2026-04-08",
        "content": "这是一段爬取正文。",
        "category": "测试",
    }

    worker = ImportWorker([article])
    worker.run()

    docs = DocumentDAO.get_all()
    assert len(docs) == 1
    doc_path = Path(docs[0].file_path)
    assert doc_path.exists()
    assert doc_path.name != "crawled"
    assert doc_path.read_text(encoding="utf-8") == article["content"]
    doc_path.unlink(missing_ok=True)
