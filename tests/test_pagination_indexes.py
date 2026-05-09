"""Database index and pagination tests."""
from sqlalchemy import inspect

from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO, TemplateDAO
from db.models import Base, engine, init_db


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def teardown_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_entity_table_has_lookup_indexes():
    indexes = inspect(engine).get_indexes("entities")
    indexed_columns = {tuple(index["column_names"]) for index in indexes}

    assert ("document_id",) in indexed_columns
    assert ("entity_type",) in indexed_columns
    assert ("entity_value",) in indexed_columns


def test_init_db_backfills_missing_entity_indexes():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(10) NOT NULL,
                file_path TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_value TEXT NOT NULL,
                context TEXT,
                confidence FLOAT
            )
            """
        )

    init_db()
    indexed_columns = {tuple(index["column_names"]) for index in inspect(engine).get_indexes("entities")}

    assert ("document_id",) in indexed_columns
    assert ("entity_type",) in indexed_columns
    assert ("entity_value",) in indexed_columns


def test_dao_get_all_accepts_limit_and_offset():
    for idx in range(5):
        DocumentDAO.create(f"doc{idx}.txt", "txt", f"/tmp/doc{idx}.txt")

    docs = DocumentDAO.get_all(limit=2, offset=1)

    assert len(docs) == 2


def test_entity_get_all_search_and_document_filters_accept_pagination():
    doc = DocumentDAO.create("doc.txt", "txt", "/tmp/doc.txt")
    EntityDAO.create_batch(
        doc.id,
        [{"type": "person", "value": f"person-{idx}", "confidence": 0.9} for idx in range(5)],
    )

    assert len(EntityDAO.get_all(limit=2, offset=1)) == 2
    assert len(EntityDAO.get_by_document(doc.id, limit=2, offset=1)) == 2
    assert len(EntityDAO.search("person", limit=2, offset=2)) == 2


def test_template_and_article_get_all_accept_pagination():
    for idx in range(4):
        TemplateDAO.create(f"tpl{idx}.xlsx", f"/tmp/tpl{idx}.xlsx", "{}")
        CrawledArticleDAO.create(f"title-{idx}", "author", "source", f"http://example.com/{idx}", "2026-05-01", "content")

    assert len(TemplateDAO.get_all(limit=2, offset=1)) == 2
    assert len(CrawledArticleDAO.get_all(limit=2, offset=1)) == 2
