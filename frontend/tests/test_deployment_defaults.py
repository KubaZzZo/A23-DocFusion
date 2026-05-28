import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import DocFusionApiClient
from server_task_client import DEFAULT_SERVER_TASK_URL, load_server_task_config


def test_main_api_client_defaults_to_local_backend_for_desktop_development():
    assert DocFusionApiClient().base_url == "http://127.0.0.1:8000/api"


def test_server_task_client_defaults_to_loopback_proxy_target(tmp_path):
    assert DEFAULT_SERVER_TASK_URL == "http://127.0.0.1:8010"
    loaded = load_server_task_config(tmp_path / "missing.json")
    assert loaded.base_url == "http://127.0.0.1:8010"
