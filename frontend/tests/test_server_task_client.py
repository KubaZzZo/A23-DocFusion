import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server_task_client import ServerTaskClient, ServerTaskConfig, load_server_task_config, save_server_task_config


def test_server_task_config_round_trips_to_json_file(tmp_path):
    path = tmp_path / "server-task.json"

    save_server_task_config(ServerTaskConfig(base_url="http://example.test:8010", token="secret"), path)
    loaded = load_server_task_config(path)

    assert loaded.base_url == "http://example.test:8010"
    assert loaded.token == "secret"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "base_url": "http://example.test:8010",
        "token": "secret",
    }


def test_server_task_config_uses_defaults_for_missing_file(tmp_path):
    loaded = load_server_task_config(tmp_path / "missing.json")

    assert loaded.base_url == "http://186.241.72.140:8010"
    assert loaded.token == ""


def test_server_task_config_loads_project_defaults_before_user_overrides(tmp_path):
    defaults = tmp_path / "defaults.json"
    user = tmp_path / "user.json"
    defaults.write_text(
        json.dumps({"base_url": "http://project.example:8010", "token": ""}),
        encoding="utf-8",
    )
    user.write_text(json.dumps({"token": "local-secret"}), encoding="utf-8")

    loaded = load_server_task_config(user, defaults)

    assert loaded.base_url == "http://project.example:8010"
    assert loaded.token == "local-secret"


def test_server_task_multipart_escapes_unsafe_filename(tmp_path):
    unsafe = tmp_path / "bad;name.docx"
    unsafe.write_bytes(b"payload")

    request = ServerTaskClient("http://example.test", "token")._multipart_request(
        "/api/server-tasks",
        {"instruction": "parse"},
        [unsafe],
    )
    body = request.data.decode("utf-8", errors="replace")

    assert 'filename="bad%3Bname.docx"' in body
    assert "filename*=UTF-8''bad%3Bname.docx" in body
    assert 'filename="bad;name.docx"' not in body
