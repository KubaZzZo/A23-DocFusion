# DocFusion Qt Redesign

This folder contains the redesigned PySide6 frontend integrated with the
DocFusion backend project.

## Run

From the repository root:

```powershell
python .\docfusion_desktop\frontend\main.py
```

The frontend can start the local FastAPI backend from the settings page, or it
can connect to an already running backend at `http://127.0.0.1:8000/api`.

The server task page uses `frontend/server_task.defaults.json` for the default
server toolkit API address. Keep the shared URL there, but save the real Bearer
token from the UI so it stays in the local user config instead of the project
repository.

## Scope

- Uses the existing backend modules for documents, entities, templates,
  articles, crawling, and LLM provider settings.
- Keeps the legacy `ui/` folder unchanged.
- Stores runtime data in the bundled backend `data/` folder.
