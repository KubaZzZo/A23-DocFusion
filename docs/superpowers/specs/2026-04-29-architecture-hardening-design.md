# Architecture Hardening Design

## Goal

Improve DocFusion maintainability without changing user-facing commands or UI behavior.

## Scope

This pass covers three focused seams:

1. Settings storage and runtime config are separated from the PyQt settings dialog.
2. Database engine/session binding can be replaced in tests and restored afterward.
3. LLM JSON parsing and entity-shape normalization are centralized.

## Design

Create a small settings module that owns `settings.json` load/save, API key encoding, and applying persisted settings to `LLM_CONFIG`. `ui.settings_dialog` keeps existing names for compatibility but delegates to this module.

Extend `db.models` with explicit database binding helpers. The default SQLite path remains `data/docfusion.db`, while tests can bind to a temporary SQLite URL and restore the default.

Add an LLM JSON utility module for code-fence stripping, parse errors, and entity-result normalization. `BaseLLM.extract_json` uses the parsing helper first; entity extraction can then opt into normalized entity results.

## Test Plan

Add failing tests first:

- Settings store can save, load, encode, decode, and apply settings without importing UI widgets.
- Database binding can switch to a temporary SQLite file and isolate DAO writes.
- LLM JSON utility returns stable parse errors and normalizes malformed entity payloads.

Existing commands remain:

```bash
python main.py
python -m api.server
pytest tests
```
