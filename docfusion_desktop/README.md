# DocFusion Desktop Package

This package keeps the redesigned desktop UI and the backend code it needs in a
small, tidy structure:

- `frontend/` - redesigned PySide6 Qt UI
- `backend/` - backend modules used by the desktop UI

## Run

From the repository root:

```powershell
python .\docfusion_desktop\frontend\main.py
```

The frontend resolves `docfusion_desktop/backend` first, so it can run without
depending on the repository root layout.
