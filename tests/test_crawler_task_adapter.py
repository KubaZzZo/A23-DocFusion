"""Crawler task adapter tests."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ui.crawler_task_adapter import CrawlerTaskAdapter


class FakeExtractor:
    instances = 0

    def __init__(self):
        FakeExtractor.instances += 1

    async def extract(self, content: str) -> dict:
        return {"entities": [{"type": "person", "value": "Alice"}]}


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
        cls.get_by_id(doc_id).raw_text = raw_text

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


def setup_function():
    FakeExtractor.instances = 0
    FakeDocumentDAO.docs = []
    FakeArticleDAO.articles = []
    FakeEntityDAO.batches = []


def make_adapter() -> CrawlerTaskAdapter:
    return CrawlerTaskAdapter(
        article_dao=FakeArticleDAO,
        document_dao=FakeDocumentDAO,
        entity_dao=FakeEntityDAO,
        document_workflow_cls=FakeDocumentWorkflow,
        entity_extractor_cls=FakeExtractor,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
    )


def make_article(title: str, content: str = "body") -> dict:
    return {
        "title": title,
        "author": "author",
        "source": "source",
        "url": f"http://example.com/{title}",
        "publish_date": "2026-05-01",
        "content": content,
        "category": "test",
    }


def test_adapter_imports_articles_and_reports_progress():
    progress_events = []

    result = make_adapter().import_articles([make_article("one")], progress_events.append)

    assert result == {"entity_count": 1, "processed": 1, "total": 1, "cancelled": False}
    assert progress_events == [{"current": 1, "total": 1}]
    assert len(FakeArticleDAO.articles) == 1
    assert len(FakeDocumentDAO.docs) == 1
    assert FakeDocumentDAO.docs[0].raw_text == "body"
    assert FakeEntityDAO.batches == [(1, [{"type": "person", "value": "Alice"}])]


def test_adapter_honors_cancel_between_articles():
    progress_events = []

    def cancel_after_first():
        return bool(progress_events)

    result = make_adapter().import_articles(
        [make_article("one"), make_article("two")],
        progress_events.append,
        cancel_after_first,
    )

    assert result["cancelled"] is True
    assert result["processed"] == 1
    assert result["total"] == 2
