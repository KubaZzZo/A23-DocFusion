import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.server import app
from api.routes import ApiWorkflows, get_workflows
from db.models import configure_database, init_db, reset_database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    configure_database(f"sqlite:///{tmp_path / 'docfusion.db'}")
    monkeypatch.setenv("DOCFUSION_API_TOKEN", "template-fill-test-token")
    init_db()
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        reset_database()


def test_fill_template_returns_controlled_error_for_malformed_task_payload(client, monkeypatch):
    class FakeTemplateWorkflow:
        def create_fill_task(self, template_id, document_ids):
            return {"task_id": 1, "status": "pending"}

    app.dependency_overrides[get_workflows] = lambda: ApiWorkflows(template=FakeTemplateWorkflow())

    try:
        response = client.post(
            "/api/templates/fill",
            headers={"Authorization": "Bearer template-fill-test-token"},
            json={"template_id": 1, "document_ids": []},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["detail"] == "模板填写任务创建失败"
