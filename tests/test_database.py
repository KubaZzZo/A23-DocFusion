"""数据库DAO测试"""
import pytest
from db.models import init_db, Base, engine
from db.database import DocumentDAO, EntityDAO, TemplateDAO, CrawledArticleDAO


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重建数据库"""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


class TestDocumentDAO:
    def test_create_and_get(self):
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        assert doc.id is not None
        assert doc.filename == "test.txt"

        fetched = DocumentDAO.get_by_id(doc.id)
        assert fetched is not None
        assert fetched.filename == "test.txt"

    def test_get_all(self):
        DocumentDAO.create("a.txt", "txt", "/tmp/a.txt")
        DocumentDAO.create("b.txt", "txt", "/tmp/b.txt")
        docs = DocumentDAO.get_all()
        assert len(docs) >= 2

    def test_update_text(self):
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        DocumentDAO.update_text(doc.id, "hello world")
        updated = DocumentDAO.get_by_id(doc.id)
        assert updated.raw_text == "hello world"

    def test_delete(self):
        doc = DocumentDAO.create("del.txt", "txt", "/tmp/del.txt")
        DocumentDAO.delete(doc.id)
        assert DocumentDAO.get_by_id(doc.id) is None

    def test_detached_access(self):
        """验证 expunge 后属性仍可访问"""
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        # 这些访问不应抛出 DetachedInstanceError
        assert doc.filename == "test.txt"
        assert doc.file_type == "txt"
        assert doc.created_at is not None


class TestEntityDAO:
    def test_create_batch_and_query(self):
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        entities = [
            {"type": "person", "value": "张三", "context": "负责人张三", "confidence": 0.9},
            {"type": "organization", "value": "测试公司", "context": "测试公司开发", "confidence": 0.85},
        ]
        EntityDAO.create_batch(doc.id, entities)

        result = EntityDAO.get_by_document(doc.id)
        assert len(result) == 2

    def test_get_all(self):
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [{"type": "person", "value": "李四", "confidence": 0.8}])
        all_entities = EntityDAO.get_all()
        assert len(all_entities) >= 1

    def test_search(self):
        doc = DocumentDAO.create("test.txt", "txt", "/tmp/test.txt")
        EntityDAO.create_batch(doc.id, [
            {"type": "person", "value": "王五", "confidence": 0.9},
            {"type": "organization", "value": "华为公司", "confidence": 0.8},
        ])
        results = EntityDAO.search("王五")
        assert len(results) == 1
        assert results[0].entity_value == "王五"

    def test_get_cross_document_entities(self):
        doc1 = DocumentDAO.create("doc1.txt", "txt", "/tmp/doc1.txt")
        doc2 = DocumentDAO.create("doc2.txt", "txt", "/tmp/doc2.txt")
        doc3 = DocumentDAO.create("doc3.txt", "txt", "/tmp/doc3.txt")
        EntityDAO.create_batch(doc1.id, [
            {"type": "person", "value": "张三", "confidence": 0.9},
            {"type": "phone", "value": "13800138000", "confidence": 0.95},
        ])
        EntityDAO.create_batch(doc2.id, [
            {"type": "person", "value": "张三", "confidence": 0.8},
        ])
        EntityDAO.create_batch(doc3.id, [
            {"type": "person", "value": "李四", "confidence": 0.85},
        ])

        results = EntityDAO.get_cross_document_entities()
        assert len(results) == 1
        assert results[0]["type"] == "person"
        assert results[0]["value"] == "张三"
        assert results[0]["doc_count"] == 2
        assert set(results[0]["documents"]) == {"doc1.txt", "doc2.txt"}


class TestTemplateDAO:
    def test_create_and_get(self):
        tpl = TemplateDAO.create("tpl.xlsx", "/tmp/tpl.xlsx", '{"fields": []}')
        assert tpl.id is not None
        fetched = TemplateDAO.get_by_id(tpl.id)
        assert fetched.filename == "tpl.xlsx"

    def test_get_all(self):
        TemplateDAO.create("a.xlsx", "/tmp/a.xlsx")
        TemplateDAO.create("b.xlsx", "/tmp/b.xlsx")
        templates = TemplateDAO.get_all()
        assert len(templates) >= 2


class TestCrawledArticleDAO:
    def test_create_and_get(self):
        article = CrawledArticleDAO.create(
            title="测试新闻", author="记者", source="新华网",
            url="http://example.com", publish_date="2026-03-18", content="新闻内容"
        )
        assert article.id is not None
        fetched = CrawledArticleDAO.get_by_id(article.id)
        assert fetched.title == "测试新闻"

    def test_create_batch(self):
        articles = [
            {"title": "新闻1", "author": "A", "source": "S", "url": "http://1.com",
             "publish_date": "2026-01-01", "content": "内容1"},
            {"title": "新闻2", "author": "B", "source": "S", "url": "http://2.com",
             "publish_date": "2026-01-02", "content": "内容2"},
        ]
        result = CrawledArticleDAO.create_batch(articles)
        assert len(result) == 2
        all_articles = CrawledArticleDAO.get_all()
        assert len(all_articles) >= 2
