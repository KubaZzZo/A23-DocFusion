#!/bin/sh
set -eu

mkdir -p "${DOCFUSION_TASKS_ROOT:-/var/docfusion/tasks}"

exec uvicorn server_toolkit.asgi:app \
  --host "${DOCFUSION_HOST:-0.0.0.0}" \
  --port "${DOCFUSION_PORT:-8010}" \
  --loop asyncio \
  --http h11
