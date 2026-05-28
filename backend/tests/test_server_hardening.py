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
