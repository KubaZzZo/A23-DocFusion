"""Small deployment checks used by VPS setup scripts and tests."""

from __future__ import annotations

from pathlib import Path


def secret_file_is_owner_only(path: str | Path) -> bool:
    """Return True when a secret file is readable/writable only by its owner."""
    secret = Path(path)
    try:
        mode = secret.stat().st_mode & 0o777
    except OSError:
        return False
    return secret_mode_is_owner_only(mode)


def secret_mode_is_owner_only(mode: int) -> bool:
    return (mode & 0o777) == 0o600
