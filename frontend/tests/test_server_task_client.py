import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server_task_client import ServerTaskConfig, load_server_task_config, save_server_task_config


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
