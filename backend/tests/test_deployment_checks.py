import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deployment_checks import secret_file_is_owner_only, secret_mode_is_owner_only


def test_secret_mode_permission_check_requires_0600():
    assert secret_mode_is_owner_only(0o644) is False
    assert secret_mode_is_owner_only(0o640) is False
    assert secret_mode_is_owner_only(0o600) is True


def test_secret_file_permission_check_rejects_missing_file(tmp_path):
    assert secret_file_is_owner_only(tmp_path / "missing.env") is False
