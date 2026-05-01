"""Crawler import workflow tests."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ui import crawler_panel
from ui.crawler_panel import CrawlerPanel


class FakeExtractor:
    instances = 0

    def __init__(self):
        FakeExtractor.instances += 1

    async def extract(self, content: str) -> dict:
        return {"entities": []}


class FakeDocumentDAO:
    docs = []

    @classmethod
    def create(cls, filename: str, file_type: str, file_path: str):
        doc = SimpleNamespace(
            id=len(cls.docs) + 1,
            filename=filename,
            file_type=file_type,
            file_path=file_path,
            raw_text="",
        )
        cls.docs.append(doc)
        return doc

    @classmethod
    def update_text(cls, doc_id: int, raw_text: str):
        for doc in cls.docs:
            if doc.id == doc_id:
                doc.raw_text = raw_text
                return

    @classmethod
    def get_all(cls):
        return list(cls.docs)

    @classmethod
    def get_by_id(cls, doc_id: int):
        return next((doc for doc in cls.docs if doc.id == doc_id), None)


class FakeArticleDAO:
    articles = []

    @classmethod
    def create_batch(cls, articles):
        cls.articles = list(articles)
        return list(articles)


class FakeEntityDAO:
    batches = []

    @classmethod
    def create_batch(cls, doc_id: int, entities: list[dict]):
        cls.batches.append((doc_id, list(entities)))


class FakeDocumentWorkflow:
    def __init__(self, upload_dir: Path):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def upload_document(self, filename: str, content: bytes):
        file_path = self.upload_dir / filename
        file_path.write_bytes(content)
        doc = FakeDocumentDAO.create(filename, "txt", str(file_path))
        return {"id": doc.id, "filename": doc.filename, "file_type": doc.file_type, "path": doc.file_path}

    def parse_document(self, doc_id: int):
        doc = next(d for d in FakeDocumentDAO.docs if d.id == doc_id)
        raw_text = Path(doc.file_path).read_text(encoding="utf-8")
        FakeDocumentDAO.update_text(doc_id, raw_text)
        return {"doc_id": doc_id, "text_length": len(raw_text)}


def setup_function():
    FakeDocumentDAO.docs = []
    FakeArticleDAO.articles = []
    FakeEntityDAO.batches = []
    FakeExtractor.instances = 0


def make_test_crawled_dir() -> Path:
    test_dir = Path("tests/.tmp_crawled") / uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def test_import_task_stores_crawled_article_as_real_file(monkeypatch):
    monkeypatch.setattr(crawler_panel, "EntityExtractor", FakeExtractor)
    monkeypatch.setattr(crawler_panel, "DocumentDAO", FakeDocumentDAO)
    monkeypatch.setattr(crawler_panel, "CrawledArticleDAO", FakeArticleDAO)
    monkeypatch.setattr(crawler_panel, "EntityDAO", FakeEntityDAO)
    monkeypatch.setattr(crawler_panel, "DocumentWorkflow", FakeDocumentWorkflow)
    monkeypatch.setattr(crawler_panel, "CRAWLED_DIR", make_test_crawled_dir())
    article = {
        "title": "测试新闻标题",
        "author": "作者",
        "source": "来源",
        "url": "http://example.com/article",
        "publish_date": "2026-04-08",
        "content": "这是一段爬取正文。",
        "category": "测试",
    }

    progress_events = []
    entity_count = CrawlerPanel._run_import_task([article], progress_events.append)

    docs = FakeDocumentDAO.get_all()
    assert len(docs) == 1
    doc_path = Path(docs[0].file_path)
    assert doc_path.exists()
    assert doc_path.name != "crawled"
    assert doc_path.read_text(encoding="utf-8") == article["content"]
    assert entity_count == 0
    assert progress_events == [{"current": 1, "total": 1}]


def test_import_task_reuses_single_extractor_for_multiple_articles(monkeypatch):
    monkeypatch.setattr(crawler_panel, "EntityExtractor", FakeExtractor)
    monkeypatch.setattr(crawler_panel, "DocumentDAO", FakeDocumentDAO)
    monkeypatch.setattr(crawler_panel, "CrawledArticleDAO", FakeArticleDAO)
    monkeypatch.setattr(crawler_panel, "EntityDAO", FakeEntityDAO)
    monkeypatch.setattr(crawler_panel, "DocumentWorkflow", FakeDocumentWorkflow)
    monkeypatch.setattr(crawler_panel, "CRAWLED_DIR", make_test_crawled_dir())
    articles = [
        {
            "title": "文章1",
            "author": "作者",
            "source": "来源",
            "url": "http://example.com/1",
            "publish_date": "2026-04-14",
            "content": "正文1",
            "category": "测试",
        },
        {
            "title": "文章2",
            "author": "作者",
            "source": "来源",
            "url": "http://example.com/2",
            "publish_date": "2026-04-14",
            "content": "正文2",
            "category": "测试",
        },
    ]

    CrawlerPanel._run_import_task(articles, lambda event: None)

    assert FakeExtractor.instances == 1
