# DocFusion Server Toolkit

This folder is the first implementation slice for the server-side document toolkit described in `../server_toolkit_plan`.

It is intentionally independent from the existing desktop `backend/` and `frontend/` code. The first version provides:

- a small `server_toolkit` Python package
- a `docfusion`-style CLI entry point
- a JSON task-plan model
- a local worker executor for `task.json`
- task workspace helpers for `input/`, `work/`, `output/`, `logs/`
- a synchronous task service for submit/status/log/download flows
- an in-memory background queue for non-blocking task submission
- a minimal FastAPI app for `/api/server-tasks`
- a deterministic L1/L2 natural-language plan parser
- local and Docker dry-run runner abstractions
- Codex L3 prompt/validation helpers
- Docker worker command construction for L1/L2 and L3 workers
- deterministic document tools for L1/L2 tasks

## Supported Commands

```text
docfusion execute        Execute a task.json plan
docfusion copy           Copy a file
docfusion convert        Convert supported document formats
docfusion format-docx    Update heading/body font settings in docx files
docfusion extract        Extract text from txt/md/csv/docx/xlsx/pdf
docfusion merge          Merge txt or PDF files
docfusion split          Extract page ranges from PDF files
docfusion fill-template  Fill xlsx headers or docx {{field}} placeholders from JSON
docfusion generate       Generate docx/txt/md documents from JSON sections
docfusion analyze        Summarize CSV/xlsx rows, columns, and numeric fields
docfusion ocr            OCR image files when Tesseract is available
docfusion validate       Check file existence, size, suffix, and basic signature
```

Some commands call optional system tools. `convert` to Office/PDF requires LibreOffice, Markdown/HTML conversion requires Pandoc, and `ocr` requires Tesseract.

`extract` also supports a lightweight `--schema field_a,field_b` mode for labeled text like `field_a: value`. This is intentionally deterministic; LLM-based extraction belongs in the later backend/Agent layer.

Several common L1/L2 conversions are handled without external binaries: txt/md/csv passthrough conversion, txt/md to docx, docx to txt/md, xlsx to csv, docx merge, PDF split/merge, template fill, and table analysis.

## Docker Runtime Contract

`server_toolkit.docker_runtime.build_docker_command()` builds argv lists for later schedulers without executing Docker.

- L1/L2 workers use `--network none`, `docfusion-worker:latest`, `2g` memory, and `/entrypoint.sh`.
- L3 workers use `docfusion-agent:latest`, `4g` memory, `/entrypoint-agent.sh`, and require an API-key environment variable name.
- All workers mount only the task workspace paths: `input:ro`, `work`, `output`, `logs`, and `task.json:ro`.

## Task Service

`server_toolkit.task_service.TaskService` provides the local execution flow that the later FastAPI layer can wrap:

```text
submit(plan, files, task_id=...) -> queued task + workspace
run_local(task_id)               -> execute task.json with the Python worker
get_status(task_id)              -> read status.json
get_logs(task_id)                -> read logs/steps.jsonl
collect_download(task_id)        -> return file or zip result
```

It is synchronous by design. The next layer can run it in a background thread, queue, or Docker scheduler without changing the task workspace contract.

## FastAPI App

`server_toolkit.api_app.create_app(tasks_root)` exposes a minimal local-worker API:

```text
POST /api/server-tasks             multipart: plan JSON or instruction + files[]
GET  /api/server-tasks             list tasks
GET  /api/server-tasks/{task_id}   status.json
GET  /api/server-tasks/{task_id}/events
GET  /api/server-tasks/{task_id}/logs
GET  /api/server-tasks/{task_id}/download
DELETE /api/server-tasks/{task_id} mark cancelled
```

The current API submits to an in-memory background queue and executes with the local Python worker by default. Docker execution is represented by a dry-run runner until a server runtime is available.

## Plan Parser and Runners

`server_toolkit.plan_parser.parse_instruction()` maps clear L1/L2 natural-language requests into deterministic task plans. It supports simple conversion, merge, extract, and table analysis requests. Ambiguous requests raise `PLAN_UNRESOLVED` instead of falling through to an agent.

`server_toolkit.runners.LocalRunner` runs the current Python worker. `DockerRunner(dry_run=True)` returns the Docker argv that would be used by a scheduler without starting Docker.

`server_toolkit.agent` only provides L3 validation and prompt construction. Codex CLI is not invoked by default.

## Layout

```text
server_toolkit/
  README.md
  server_toolkit/
    __init__.py
    api_app.py
    agent.py
    cli.py
    docker_runtime.py
    plan_parser.py
    runners.py
    task_models.py
    task_queue.py
    task_service.py
    tools.py
    worker.py
    workspace.py
  tests/
```

## Run Tests

From the repository root:

```powershell
python -m pytest docfusion_desktop/server_toolkit/tests -q
```

## Standalone Docker API

Build the standalone API image from this folder:

```powershell
docker build -t docfusion-toolkit-api:latest docfusion_desktop/server_toolkit
```

Run it on a separate port with a Bearer token:

```powershell
docker run -d --name docfusion-toolkit-api `
  -p 8010:8010 `
  -e DOCFUSION_API_TOKEN=change-this-token `
  -v docfusion_tasks:/var/docfusion/tasks `
  docfusion-toolkit-api:latest
```

On the current VPS, keep task files on the data disk instead of the root disk:

```bash
mkdir -p /data/docfusion/tasks
docker run -d --name docfusion-toolkit-api \
  --restart unless-stopped \
  --network host \
  --memory 1g \
  --cpus 1.5 \
  --env-file /opt/docfusion-toolkit/.env \
  -e DOCFUSION_TASKS_ROOT=/var/docfusion/tasks \
  -v /data/docfusion/tasks:/var/docfusion/tasks \
  docfusion-toolkit-api:latest
```

This host uses port `8010` from the container entrypoint. The existing `new-api` container stays on port `3000`.

Health check:

```powershell
curl http://127.0.0.1:8010/healthz
```

All `/api/server-tasks` routes require `Authorization: Bearer <token>` when `DOCFUSION_API_TOKEN` is set. `/healthz` stays open for container health checks.

## Run a Task

The worker expects a workspace shaped like the server plan:

```text
workspace/
  input/
  work/
  output/
  logs/
  task.json
```

Run:

```powershell
python -m server_toolkit.cli execute path\to\workspace\task.json --workspace path\to\workspace
```

When this package is installed later, the command name should be exposed as `docfusion`.
