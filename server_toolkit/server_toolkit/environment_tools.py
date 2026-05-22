"""Runtime environment checks for the server toolkit image."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


DEFAULT_TOOL_COMMANDS: dict[str, list[str]] = {
    "libreoffice": ["libreoffice", "--version"],
    "pandoc": ["pandoc", "--version"],
    "tesseract": ["tesseract", "--version"],
}


def check_environment_tools(commands: dict[str, list[str]] | None = None) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for name, argv in (commands or DEFAULT_TOOL_COMMANDS).items():
        executable = shutil.which(argv[0])
        if not executable:
            report[name] = {
                "available": False,
                "path": None,
                "version": None,
                "error": "executable not found",
            }
            continue
        try:
            completed = subprocess.run(
                [executable, *argv[1:]],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            report[name] = {
                "available": False,
                "path": executable,
                "version": None,
                "error": str(exc),
            }
            continue
        output = (completed.stdout or completed.stderr or "").splitlines()
        report[name] = {
            "available": True,
            "path": executable,
            "version": output[0].strip() if output else None,
            "error": None,
        }
    return report
