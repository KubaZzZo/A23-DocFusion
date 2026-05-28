import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.auth as auth


def test_get_api_token_secures_new_token_file(tmp_path, monkeypatch):
    token_file = tmp_path / "api_token.txt"
    calls = []

    monkeypatch.delenv(auth.TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(auth, "_secure_token_file", lambda path: calls.append(Path(path)))

    token = auth.get_api_token(token_file)

    assert token
    assert token_file.read_text(encoding="utf-8") == token
    assert calls == [token_file]


def test_get_api_token_secures_existing_token_file(tmp_path, monkeypatch):
    token_file = tmp_path / "api_token.txt"
    token_file.write_text("existing-token", encoding="utf-8")
    calls = []

    monkeypatch.delenv(auth.TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(auth, "_secure_token_file", lambda path: calls.append(Path(path)))

    token = auth.get_api_token(token_file)

    assert token == "existing-token"
    assert calls == [token_file]


def test_windows_token_acl_restricts_file_inheritance(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(auth.os, "name", "nt")
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.setattr(auth.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

    auth._secure_token_file(tmp_path / "api_token.txt")

    args, kwargs = calls[0]
    assert args[:3] == ["icacls", str(tmp_path / "api_token.txt"), "/inheritance:r"]
    assert "/grant:r" in args
    assert "alice:F" in args
    assert kwargs["check"] is False
