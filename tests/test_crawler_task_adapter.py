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


class ParseErrorExtractor:
    async def extract(self, content: str) -> dict:
        return {"parse_error": "model returned invalid payload", "entities": []}


class EmptyEntityExtractor:
    async def extract(self, content: str) -> dict:
        return {"entities": []}


class FakeSpider:
    def __init__(self):
        self.closed = False

    def fetch_article_detail(self, article: dict) -> dict:
        refreshed = dict(article)
        refreshed["content"] = "refetched body"
        return refreshed

    def close(self):
        self.closed = True


class FailingSpider(FakeSpider):
    def fetch_article_detail(self, article: dict) -> dict:
        raise RuntimeError("detail fetch failed")


class FakeDocumentDAO:
    docs = []

    @classmethod
    def create(cls, filename: str, file_type: str, file_path: str, session=None):
        doc = SimpleNamespace(
            id=len(cls.docs) + 1,
            filename=filename,
            file_type=file_type,
            file_path=file_path,
            raw_text="",
        )
        if session is not None:
            session.add_document(doc)
        else:
            cls.docs.append(doc)
        return doc

    @classmethod
    def update_text(cls, doc_id: int, raw_text: str, session=None):
        cls.get_by_id(doc_id, session=session).raw_text = raw_text

    @classmethod
    def get_by_id(cls, doc_id: int, session=None):
        docs = cls.docs if session is None else session.documents
        return next((doc for doc in docs if doc.id == doc_id), None)


class FakeArticleDAO:
    articles = []

    @classmethod
    def create_batch(cls, articles):
        cls.articles = list(articles)
        return list(articles)


class FakeEntityDAO:
    batches = []

    @classmethod
    def create_batch(cls, doc_id: int, entities: list[dict], session=None):
        cls.batches.append((doc_id, list(entities)))


class FailingEntityDAO:
    @classmethod
    def create_batch(cls, doc_id: int, entities: list[dict], session=None):
        raise RuntimeError("entity write failed")


class FakeDocumentWorkflow:
    def __init__(self, upload_dir: Path):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def upload_document(self, filename: str, content: bytes):
        file_path = self.upload_dir / filename
        file_path.write_bytes(content)
        doc = FakeDocumentDAO.create(filename, "txt", str(file_path))
        return {"id": doc.id, "filename": doc.filename, "file_type": doc.file_type, "path": doc.file_path}


class FakeSession:
    def __init__(self):
        self.documents = []

    def add_document(self, doc):
        self.documents.append(doc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            FakeDocumentDAO.docs.extend(self.documents)
        return False


def fake_session_scope():
    return FakeSession()


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
        spider_cls=FakeSpider,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
        session_scope_factory=fake_session_scope,
    )


def make_failing_entity_adapter() -> CrawlerTaskAdapter:
    return CrawlerTaskAdapter(
        article_dao=FakeArticleDAO,
        document_dao=FakeDocumentDAO,
        entity_dao=FailingEntityDAO,
        document_workflow_cls=FakeDocumentWorkflow,
        entity_extractor_cls=FakeExtractor,
        spider_cls=FakeSpider,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
        session_scope_factory=fake_session_scope,
    )


def make_parse_error_adapter() -> CrawlerTaskAdapter:
    return CrawlerTaskAdapter(
        article_dao=FakeArticleDAO,
        document_dao=FakeDocumentDAO,
        entity_dao=FakeEntityDAO,
        document_workflow_cls=FakeDocumentWorkflow,
        entity_extractor_cls=ParseErrorExtractor,
        spider_cls=FakeSpider,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
        session_scope_factory=fake_session_scope,
    )


def make_empty_entity_adapter() -> CrawlerTaskAdapter:
    return CrawlerTaskAdapter(
        article_dao=FakeArticleDAO,
        document_dao=FakeDocumentDAO,
        entity_dao=FakeEntityDAO,
        document_workflow_cls=FakeDocumentWorkflow,
        entity_extractor_cls=EmptyEntityExtractor,
        spider_cls=FakeSpider,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
        session_scope_factory=fake_session_scope,
    )


def make_missing_content_adapter(spider_cls=FakeSpider) -> CrawlerTaskAdapter:
    return CrawlerTaskAdapter(
        article_dao=FakeArticleDAO,
        document_dao=FakeDocumentDAO,
        entity_dao=FakeEntityDAO,
        document_workflow_cls=FakeDocumentWorkflow,
        entity_extractor_cls=FakeExtractor,
        spider_cls=spider_cls,
        crawled_dir=Path("tests/.tmp_crawled") / uuid4().hex,
        session_scope_factory=fake_session_scope,
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

    assert result["entity_count"] == 1
    assert result["processed"] == 1
    assert result["total"] == 1
    assert result["cancelled"] is False
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 0
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


def test_adapter_processes_multiple_articles_with_bounded_parallel_path():
    progress_events = []

    result = make_adapter().import_articles(
        [make_article("one"), make_article("two"), make_article("three")],
        progress_events.append,
    )

    assert result["entity_count"] == 3
    assert result["processed"] == 3
    assert result["total"] == 3
    assert result["cancelled"] is False
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 0
    assert len(FakeDocumentDAO.docs) == 3
    assert len(FakeEntityDAO.batches) == 3
    assert progress_events[-1] == {"current": 3, "total": 3}


def test_adapter_rolls_back_document_when_entity_write_fails():
    progress_events = []

    result = make_failing_entity_adapter().import_articles([make_article("one")], progress_events.append)

    assert result["entity_count"] == 0
    assert result["processed"] == 1
    assert result["total"] == 1
    assert result["cancelled"] is False
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 1
    assert result["zero_entity_count"] == 0
    assert FakeDocumentDAO.docs == []
    assert progress_events == [{"current": 1, "total": 1}]


def test_adapter_reports_empty_content_separately():
    progress_events = []

    result = make_missing_content_adapter(FailingSpider).import_articles([make_article("empty", "")], progress_events.append)

    assert result["entity_count"] == 0
    assert result["processed"] == 1
    assert result["empty_content_count"] == 1
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 0
    assert progress_events == [{"current": 1, "total": 1}]


def test_adapter_refetches_missing_content_before_extracting():
    progress_events = []

    result = make_missing_content_adapter().import_articles([make_article("empty", "")], progress_events.append)

    assert result["entity_count"] == 1
    assert result["processed"] == 1
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 0
    assert result["refetched_content_count"] == 1
    assert FakeDocumentDAO.docs[0].raw_text == "refetched body"


def test_adapter_marks_missing_content_as_failed_when_refetch_fails():
    progress_events = []

    result = make_missing_content_adapter(FailingSpider).import_articles([make_article("empty", "")], progress_events.append)

    assert result["entity_count"] == 0
    assert result["processed"] == 1
    assert result["empty_content_count"] == 1
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 0
    assert result["refetched_content_count"] == 0


def test_adapter_reports_parse_errors_separately():
    progress_events = []

    result = make_parse_error_adapter().import_articles([make_article("bad-model")], progress_events.append)

    assert result["entity_count"] == 0
    assert result["processed"] == 1
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 1
    assert result["zero_entity_count"] == 0


def test_adapter_reports_true_zero_entity_results_separately():
    progress_events = []

    result = make_empty_entity_adapter().import_articles([make_article("no-entities")], progress_events.append)

    assert result["entity_count"] == 0
    assert result["processed"] == 1
    assert result["empty_content_count"] == 0
    assert result["extract_failed_count"] == 0
    assert result["zero_entity_count"] == 1
