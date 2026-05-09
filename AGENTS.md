# Repository Guidelines

## Project Structure & Module Organization

DocFusion is a Python desktop and local API application for document understanding and data fusion. `main.py` starts logging, settings, SQLite, the PyQt6 UI, and the local FastAPI service.

- `api/`: FastAPI server and route definitions.
- `core/`: document parsing, chunking, extraction, semantic matching, workflows, and document commands.
- `crawler/`: news crawling and generated document workflows.
- `db/`: SQLAlchemy models, database setup, and session helpers.
- `llm/`: Ollama and OpenAI-compatible clients, provider presets, health checks, JSON helpers, and cache logic.
- `ui/`: PyQt6 windows, panels, dialogs, task runners, and styles.
- `utils/`: shared utility functions.
- `tests/`: pytest suites and fixtures in `tests/test_data/`.
- `data/`: runtime database, uploads, outputs, cache, logs, and backups; keep generated contents out of commits.

## Build, Test, and Development Commands

Use Python 3.12 or 3.13 on Windows.

```bash
pip install -r requirements.txt
python main.py
python -m api.server
pytest tests
pytest tests/test_parser.py -v
```

`python main.py` launches the desktop app and background API at `http://127.0.0.1:8000`. `python -m api.server` runs only the FastAPI service. Use targeted pytest commands while developing, then run `pytest tests` before submitting changes.

## Coding Style & Naming Conventions

Follow existing Python conventions: 4-space indentation, `snake_case` functions and variables, `PascalCase` classes, and lowercase module names. Keep UI-facing Chinese text consistent with nearby files. Prefer existing helpers such as `session_scope()`, DAO classes, `utils.file_utils.safe_copy()`, and the LLM factory instead of duplicating logic.

## Testing Guidelines

Tests use `pytest`. Name files `test_<feature>.py` and test functions `test_<expected_behavior>`. Add coverage for parser, database, API, UI layout, LLM parsing, crawler imports, and document-command behavior when touching those areas. Keep deterministic fixtures in `tests/test_data/`; do not depend on local runtime files from `data/`.

## Commit & Pull Request Guidelines

Recent commits use concise imperative messages, such as `Improve UI structure and text cleanup` and `Speed up crawler import`. Keep commits focused on one change.

Pull requests should include a short summary, linked issue or task when available, test results such as `pytest tests`, and screenshots for visible PyQt6 UI changes. Note configuration impacts for OCR, Ollama, cloud LLM providers, or API behavior.

## Security & Configuration Tips

Do not commit API keys, `data/settings.json`, `data/docfusion.db`, uploads, outputs, logs, caches, `.pytest_cache/`, or `__pycache__/`. Configure OCR with `TESSERACT_CMD` or `config.py`; configure cloud LLM credentials through the settings dialog or environment variables.
