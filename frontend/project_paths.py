"""Path helpers for running the redesigned Qt frontend inside or beside DocFusion."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        bundled_backend = parent / "backend"
        if (bundled_backend / "api" / "server.py").exists() and (bundled_backend / "core").is_dir():
            return bundled_backend
        if (parent / "api" / "server.py").exists() and (parent / "core").is_dir():
            return parent
        sibling = parent / "A23-DocFusion"
        if (sibling / "api" / "server.py").exists() and (sibling / "core").is_dir():
            return sibling
    return here.parents[1]
