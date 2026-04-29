# Architecture Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate settings storage, database binding, and LLM JSON normalization behind small testable modules.

**Architecture:** Preserve current public commands and imports while adding deeper modules. UI and existing callers keep compatibility wrappers where needed.

**Tech Stack:** Python, PyQt6, SQLAlchemy, pytest.

---

### Task 1: Settings Store

**Files:**
- Create: `settings_store.py`
- Modify: `ui/settings_dialog.py`
- Test: `tests/test_settings_store.py`

- [ ] Write tests for save/load/apply with a temporary settings file.
- [ ] Run `pytest tests/test_settings_store.py -v` and confirm import failure.
- [ ] Implement the settings store and delegate UI helpers to it.
- [ ] Re-run the targeted test.

### Task 2: Database Binding

**Files:**
- Modify: `db/models.py`
- Test: `tests/test_database_binding.py`

- [ ] Write tests for switching to a temporary SQLite URL and restoring default binding.
- [ ] Run `pytest tests/test_database_binding.py -v` and confirm missing helper failure.
- [ ] Implement `configure_database`, `reset_database`, and `get_database_url`.
- [ ] Re-run the targeted test.

### Task 3: LLM JSON Normalization

**Files:**
- Create: `llm/json_utils.py`
- Modify: `llm/base.py`, `core/entity_extractor.py`
- Test: `tests/test_llm_json_utils.py`

- [ ] Write tests for fenced JSON, parse errors, and entity result normalization.
- [ ] Run `pytest tests/test_llm_json_utils.py -v` and confirm missing module failure.
- [ ] Implement parsing and normalization helpers.
- [ ] Re-run the targeted test and existing LLM tests.

### Task 4: Verification

- [ ] Run `pytest tests/test_settings_store.py tests/test_database_binding.py tests/test_llm_json_utils.py tests/test_llm_json_fences.py tests/test_database.py -v`.
- [ ] Run `pytest tests` if targeted tests pass.
