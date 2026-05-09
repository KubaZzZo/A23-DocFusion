"""Configuration security hardening tests."""
import os
import stat
import subprocess

from config import DATA_DIR


def test_data_directory_is_private_to_current_user():
    if os.name == "nt":
        result = subprocess.run(["icacls", str(DATA_DIR)], check=False, capture_output=True, text=True)
        output = result.stdout
        assert "Everyone:" not in output
        assert "BUILTIN\\Users:" not in output
        return

    mode = stat.S_IMODE(DATA_DIR.stat().st_mode)

    assert mode & 0o077 == 0
