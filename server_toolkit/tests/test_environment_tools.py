import subprocess

from fastapi.testclient import TestClient

from server_toolkit.api_app import create_app
from server_toolkit.environment_tools import check_environment_tools


def test_check_environment_tools_reports_versions(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "pandoc" else None)

    def fake_run(argv, **kwargs):
        assert argv == ["/usr/bin/pandoc", "--version"]
        return subprocess.CompletedProcess(argv, 0, stdout="pandoc 3.1.11\n", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    report = check_environment_tools({"pandoc": ["pandoc", "--version"], "libreoffice": ["libreoffice", "--version"]})

    assert report["pandoc"]["available"] is True
    assert report["pandoc"]["version"] == "pandoc 3.1.11"
    assert report["libreoffice"]["available"] is False
    assert report["libreoffice"]["error"] == "executable not found"


def test_api_environment_tools_requires_auth_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "server_toolkit.api_app.check_environment_tools",
        lambda: {"pandoc": {"available": True, "version": "pandoc 3.1.11", "path": "/usr/bin/pandoc"}},
    )
    app = create_app(tmp_path / "tasks", bearer_token="secret")
    client = TestClient(app)

    rejected = client.get("/api/server-tools")
    accepted = client.get("/api/server-tools", headers={"Authorization": "Bearer secret"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["tools"]["pandoc"]["available"] is True
