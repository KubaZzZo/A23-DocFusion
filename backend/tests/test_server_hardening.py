import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_openapi_and_docs_are_not_publicly_exposed():
    from api.server import app

    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_default_tesseract_command_is_platform_specific(monkeypatch):
    import config

    assert config._default_tesseract_cmd("nt") == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    assert config._default_tesseract_cmd("posix") == "tesseract"


def test_private_dir_rejects_broken_symlink():
    import pytest

    import config

    class BrokenSymlink:
        def __init__(self):
            self.mkdir_called = False

        def is_symlink(self):
            return True

        def exists(self):
            return False

        def readlink(self):
            return "/missing-target"

        def mkdir(self, **kwargs):
            self.mkdir_called = True

        def __fspath__(self):
            return "/broken-data"

        def __str__(self):
            return "/broken-data"

    data_link = BrokenSymlink()

    with pytest.raises(RuntimeError, match="symlink target does not exist"):
        config._ensure_private_dir(data_link)

    assert not data_link.mkdir_called


def test_docfusion_logger_uses_rotating_file_handler(monkeypatch, tmp_path):
    import logging

    import logger

    test_log = tmp_path / "docfusion.log"
    root = logging.getLogger("docfusion")
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    monkeypatch.setattr(logger, "LOG_FILE", test_log)
    monkeypatch.setenv("DOCFUSION_LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("DOCFUSION_LOG_BACKUP_COUNT", "3")

    configured = logger.setup_logging()

    file_handlers = [handler for handler in configured.handlers if hasattr(handler, "maxBytes")]
    assert file_handlers
    assert file_handlers[0].maxBytes == 2048
    assert file_handlers[0].backupCount == 3

    for handler in list(configured.handlers):
        configured.removeHandler(handler)
        handler.close()


def test_llm_runtime_config_snapshot_is_isolated():
    from config import LLM_CONFIG
    from llm.runtime_config import get_llm_config_snapshot

    snapshot = get_llm_config_snapshot()
    snapshot["openai"]["model"] = "changed-in-test"

    assert LLM_CONFIG["openai"]["model"] != "changed-in-test"


def test_api_workflows_can_be_overridden_with_dependency_injection():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import api.auth as auth
    from api.routes import ApiWorkflows, get_workflows, router

    class FakeStatisticsWorkflow:
        def get_statistics(self):
            return {"documents": 123, "entities": 456}

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    app.dependency_overrides[get_workflows] = lambda: ApiWorkflows(statistics=FakeStatisticsWorkflow())
    app.dependency_overrides[auth.require_local_bearer_token] = lambda: None
    try:
        response = client.get("/api/statistics", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"documents": 123, "entities": 456}
