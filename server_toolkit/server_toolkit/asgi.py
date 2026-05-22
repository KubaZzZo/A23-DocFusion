"""ASGI entry point for the standalone server-toolkit container."""

from __future__ import annotations

import os
from pathlib import Path

from server_toolkit.api_app import create_app


TASKS_ROOT = Path(os.getenv("DOCFUSION_TASKS_ROOT", "/var/docfusion/tasks"))

app = create_app(
    TASKS_ROOT,
    max_files=int(os.getenv("DOCFUSION_MAX_FILES", "10")),
    max_file_size=int(os.getenv("DOCFUSION_MAX_FILE_SIZE", str(50 * 1024 * 1024))),
    max_total_size=int(os.getenv("DOCFUSION_MAX_TOTAL_SIZE", str(200 * 1024 * 1024))),
    max_concurrent_tasks=int(os.getenv("DOCFUSION_MAX_CONCURRENT_TASKS", "1")),
    task_queue_size=int(os.getenv("DOCFUSION_TASK_QUEUE_SIZE", "20")),
)
