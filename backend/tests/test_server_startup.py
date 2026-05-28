import importlib
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_importing_server_does_not_apply_saved_settings(monkeypatch):
    import api.server as server

    calls = []
    monkeypatch.setattr("settings_store.apply_saved_settings", lambda: calls.append("settings"))
    monkeypatch.setattr("db.models.init_db", lambda: calls.append("db"))

    reloaded = importlib.reload(server)

    assert calls == []

    reloaded.initialize_runtime()

    assert calls == ["settings", "db"]
