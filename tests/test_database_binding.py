"""Database binding isolation tests."""
import shutil
from pathlib import Path

from db import models
from db.database import DocumentDAO

TMP_DIR = Path(__file__).parent / ".tmp_database_binding"


def test_configure_database_switches_dao_to_temp_sqlite():
    TMP_DIR.mkdir(exist_ok=True)
    original_url = models.get_database_url()
    temp_url = f"sqlite:///{TMP_DIR / 'isolated.db'}"

    try:
        models.configure_database(temp_url)
        models.init_db()
        doc = DocumentDAO.create("isolated.txt", "txt", "/tmp/isolated.txt")

        assert models.get_database_url() == temp_url
        assert DocumentDAO.get_by_id(doc.id).filename == "isolated.txt"
    finally:
        models.configure_database(original_url)
        models.init_db()
        shutil.rmtree(TMP_DIR, ignore_errors=True)


def test_reset_database_restores_default_url():
    TMP_DIR.mkdir(exist_ok=True)
    original_url = models.get_database_url()
    models.configure_database(f"sqlite:///{TMP_DIR / 'other.db'}")

    try:
        models.reset_database()
        assert models.get_database_url() == original_url
    finally:
        models.configure_database(original_url)
        shutil.rmtree(TMP_DIR, ignore_errors=True)
