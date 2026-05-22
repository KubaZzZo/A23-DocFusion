import json
import time

from fastapi.testclient import TestClient

from server_toolkit.api_app import create_app


def test_api_submit_task_runs_and_returns_completed_status(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": ["input/source.txt"],
        "outputs": ["output/result.txt"],
        "timeout_seconds": 60,
        "steps": [
            {
                "id": "copy",
                "tool": "docfusion",
                "command": "copy",
                "args": {"input": "input/source.txt", "output": "output/result.txt"},
            }
        ],
    }

    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(plan)},
        files=[("files", ("source.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] in {"queued", "running"}
    task_id = payload["task_id"]
    status = _wait_for_status(client, task_id, "completed")
    assert status["output_files"] == ["output/result.txt"]
    assert status["input_files"] == ["source.txt"]
    assert status["progress"]["description"] == "completed"


def test_api_get_status_and_logs(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    task_id = _submit_copy_task(client)

    status = client.get(f"/api/server-tasks/{task_id}")
    logs = client.get(f"/api/server-tasks/{task_id}/logs")

    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert logs.status_code == 200
    assert [event["event"] for event in logs.json()["events"]] == [
        "start",
        "step_started",
        "step_completed",
        "complete",
    ]


def test_api_download_returns_result_file(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    task_id = _submit_copy_task(client)

    response = client.get(f"/api/server-tasks/{task_id}/download")

    assert response.status_code == 200
    assert response.content == b"hello"
    assert "attachment" in response.headers["content-disposition"]


def test_api_download_returns_requested_output_file(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": ["input/source.txt"],
        "outputs": ["output/a.txt", "output/b.txt"],
        "timeout_seconds": 60,
        "steps": [
            {
                "id": "copy_a",
                "tool": "docfusion",
                "command": "copy",
                "args": {"input": "input/source.txt", "output": "output/a.txt"},
            },
            {
                "id": "copy_b",
                "tool": "docfusion",
                "command": "copy",
                "args": {"input": "input/source.txt", "output": "output/b.txt"},
            },
        ],
    }
    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(plan)},
        files=[("files", ("source.txt", b"hello", "text/plain"))],
    )
    task_id = response.json()["task_id"]
    _wait_for_status(client, task_id, "completed")

    download = client.get(f"/api/server-tasks/{task_id}/download?file=output/b.txt")

    assert download.status_code == 200
    assert download.content == b"hello"
    assert 'filename="b.txt"' in download.headers["content-disposition"]


def test_api_rejects_invalid_plan(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)

    response = client.post("/api/server-tasks", data={"plan": "{}"})

    assert response.status_code == 400
    assert "level" in response.json()["error"]["message"]


def test_api_rejects_too_many_files(tmp_path):
    app = create_app(tmp_path / "tasks", max_files=1)
    client = TestClient(app)

    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(_copy_plan())},
        files=[
            ("files", ("a.txt", b"a", "text/plain")),
            ("files", ("b.txt", b"b", "text/plain")),
        ],
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_api_rejects_disallowed_extension(tmp_path):
    app = create_app(tmp_path / "tasks", allowed_extensions={"txt"})
    client = TestClient(app)

    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(_copy_plan())},
        files=[("files", ("bad.exe", b"MZ", "application/octet-stream"))],
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_TYPE"


def test_api_returns_404_for_missing_task(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)

    response = client.get("/api/server-tasks/nope")

    assert response.status_code == 404


def test_api_lists_tasks(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    task_id = _submit_copy_task(client)

    response = client.get("/api/server-tasks")

    assert response.status_code == 200
    assert [task["task_id"] for task in response.json()["tasks"]] == [task_id]


def test_api_events_returns_sse_text(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    task_id = _submit_copy_task(client)

    response = client.get(f"/api/server-tasks/{task_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: queued" in response.text
    assert "event: step_started" in response.text
    assert "event: complete" in response.text


def test_api_accepts_priority_and_timeout_metadata(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)

    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(_copy_plan()), "priority": "high", "timeout": "30"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["priority"] == "high"
    assert payload["timeout_seconds"] == 30


def test_api_healthz_does_not_require_auth(tmp_path):
    app = create_app(tmp_path / "tasks", bearer_token="secret")
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_api_rejects_missing_bearer_token_when_configured(tmp_path):
    app = create_app(tmp_path / "tasks", bearer_token="secret")
    client = TestClient(app)

    response = client.get("/api/server-tasks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_api_accepts_valid_bearer_token_when_configured(tmp_path):
    app = create_app(tmp_path / "tasks", bearer_token="secret")
    client = TestClient(app)

    response = client.get("/api/server-tasks", headers={"Authorization": "Bearer secret"})

    assert response.status_code == 200
    assert response.json()["tasks"] == []


def test_api_rejects_invalid_list_parameters(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)

    bad_status = client.get("/api/server-tasks?status=broken")
    bad_limit = client.get("/api/server-tasks?limit=0")
    bad_offset = client.get("/api/server-tasks?offset=-1")

    assert bad_status.status_code == 400
    assert bad_status.json()["error"]["code"] == "INVALID_STATUS"
    assert bad_limit.status_code == 400
    assert bad_limit.json()["error"]["code"] == "INVALID_PAGINATION"
    assert bad_offset.status_code == 400
    assert bad_offset.json()["error"]["code"] == "INVALID_PAGINATION"


def test_api_delete_task_marks_cancelled(tmp_path):
    app = create_app(tmp_path / "tasks")
    client = TestClient(app)
    task_id = _submit_copy_task(client)

    response = client.delete(f"/api/server-tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def _submit_copy_task(client: TestClient) -> str:
    plan = {
        "level": "L1",
        "requires_agent": False,
        "inputs": ["input/source.txt"],
        "outputs": ["output/result.txt"],
        "timeout_seconds": 60,
        "steps": [
            {
                "id": "copy",
                "tool": "docfusion",
                "command": "copy",
                "args": {"input": "input/source.txt", "output": "output/result.txt"},
            }
        ],
    }
    response = client.post(
        "/api/server-tasks",
        data={"plan": json.dumps(plan)},
        files=[("files", ("source.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 201
    task_id = response.json()["task_id"]
    _wait_for_status(client, task_id, "completed")
    return task_id


def _copy_plan() -> dict:
    return {
        "level": "L1",
        "requires_agent": False,
        "inputs": [],
        "outputs": [],
        "timeout_seconds": 60,
        "steps": [],
    }


def _wait_for_status(client: TestClient, task_id: str, expected: str) -> dict:
    for _ in range(50):
        status = client.get(f"/api/server-tasks/{task_id}").json()
        if status["status"] == expected:
            return status
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} did not reach {expected}")
