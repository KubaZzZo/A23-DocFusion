# Repository Guidelines

## Project Structure & Module Organization

DocFusion is a Python desktop and local API application for document understanding and data fusion. `main.py` initializes logging, settings, SQLite, the PyQt6 UI, and the local FastAPI service.

- `api/`: FastAPI server and routes.
- `core/`: parsing, chunking, extraction, semantic matching, template filling, and document commands.
- `crawler/`: news crawling and generated document workflows.
- `db/`: SQLAlchemy models, DAO helpers, and session management.
- `llm/`: Ollama and OpenAI-compatible client adapters plus cache logic.
- `ui/`: PyQt6 windows, panels, dialogs, widgets, styles.
- `utils/`: shared utility functions.
- `tests/`: pytest suites and checked-in test fixtures under `tests/test_data/`.
- `data/`: runtime database, uploads, outputs, cache, logs, backups; do not commit generated contents.

## Build, Test, and Development Commands

Use Python 3.12 or 3.13 on Windows.

```bash
pip install -r requirements.txt
python main.py
python -m api.server
pytest tests
pytest tests/test_parser.py -v
```

- `pip install -r requirements.txt`: installs UI, API, document, OCR, LLM, and crawler dependencies.
- `python main.py`: starts the desktop app and background API at `http://127.0.0.1:8000`.
- `python -m api.server`: starts only FastAPI for API development.
- `pytest tests`: runs the full test suite.

## Coding Style & Naming Conventions

Follow the existing Python style: 4-space indentation, descriptive snake_case functions and variables, PascalCase classes, and lowercase module names. Keep UI labels and user-facing project text in Chinese unless the surrounding file uses English. Prefer existing helpers such as `session_scope()`, DAO classes, `utils.file_utils.safe_copy()`, and the LLM factory.

## Testing Guidelines

Tests use `pytest`. Add or update tests in `tests/` for parser, database, API, UI layout, LLM parsing, crawler imports, and document-command behavior. Name files `test_<feature>.py` and functions `test_<expected_behavior>`. Keep fixtures in `tests/test_data/`; do not rely on local `data/` runtime files.

## Commit & Pull Request Guidelines

Recent history uses concise imperative messages, for example `Fix LLM JSON fences and crawler imports` or `Improve UX, performance, and LLM compatibility`. Keep commits focused.

Pull requests should include a short summary, linked issue or task when available, test results such as `pytest tests`, and screenshots for visible PyQt6 UI changes. Note configuration impacts for OCR, Ollama, cloud LLM providers, or API behavior.

## Security & Configuration Tips

Do not commit API keys, `data/settings.json`, `data/docfusion.db`, uploads, outputs, logs, caches, `.pytest_cache/`, or `__pycache__/`. Configure OCR with `TESSERACT_CMD` or `config.py`. Configure cloud LLM access through the settings dialog or environment variables such as `OPENAI_API_KEY`.
