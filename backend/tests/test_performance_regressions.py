import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.document_parser import DocumentParser
from db.database import DocumentDAO, EntityDAO
import db.models as db_models
from db.models import configure_database, init_db, reset_database


def test_document_parse_cache_is_small_to_avoid_large_text_memory_growth():
    assert DocumentParser._do_parse.cache_info().maxsize == 8


def test_sqlite_database_uses_wal_for_concurrent_ui_and_api_writes(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    try:
        init_db()
        with db_models.engine.connect() as conn:
            journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert str(journal_mode).lower() == "wal"
    finally:
        reset_database()


def test_cross_document_entities_limits_document_names(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    init_db()
    try:
        for index in range(12):
            doc = DocumentDAO.create(f"doc-{index:02d}.txt", "txt", str(tmp_path / f"doc-{index:02d}.txt"))
            EntityDAO.create_batch(doc.id, [{"type": "organization", "value": "Acme", "confidence": 0.9}])

        rows = EntityDAO.get_cross_document_entities(min_documents=2)

        assert rows[0]["doc_count"] == 12
        assert len(rows[0]["documents"]) == 10
        assert rows[0]["documents"] == [f"doc-{index:02d}.txt" for index in range(10)]
    finally:
        reset_database()


def test_llm_factory_reuses_clients_until_configuration_changes(monkeypatch):
    import llm.factory as factory
    from llm.runtime_config import update_llm_config

    factory.clear_llm_cache()
    created = []

    class FakeOllama:
        def __init__(self):
            created.append("ollama")

    monkeypatch.setattr(factory, "OllamaClient", FakeOllama)
    update_llm_config({"provider": "ollama", "ollama_url": "http://one", "ollama_model": "qwen2.5:7b"})

    first = factory.get_llm()
    second = factory.get_llm()
    update_llm_config({"ollama_url": "http://two"})
    third = factory.get_llm()

    assert first is second
    assert third is not first
    assert created == ["ollama", "ollama"]
