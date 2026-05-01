# Main Window Status Bar Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把主窗口顶部的 LLM 状态条抽成独立模块，让 `ui/main_window.py` 只负责装配、切换页签和启动 API。

**Architecture:** 新增一个轻量的 `ui/main_status_bar.py`，专门负责顶部状态条的构建、LLM 状态快照和同步刷新。`ui/main_window.py` 保留主窗口壳子，直接持有这个状态条实例，并把原来的 `_llm_status_snapshot` 兼容入口转成薄包装，避免现有测试和调用点断裂。

**Tech Stack:** Python 3.12, PyQt6, pytest

---

### Task 1: Extract the top status bar widget

**Files:**
- Create: `ui/main_status_bar.py`
- Modify: `ui/main_window.py:1-260`
- Test: `tests/test_main_window_status.py`

- [ ] **Step 1: Write the failing test**

```python
from ui.main_status_bar import MainStatusBar, llm_status_snapshot


def test_llm_status_snapshot_formats_ollama_runtime_config():
    config = {
        "provider": "ollama",
        "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5:7b"},
        "openai": {"vendor": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    }

    snapshot = llm_status_snapshot(config)

    assert snapshot["provider"] == "ollama"
    assert snapshot["label"] == "Ollama"
    assert snapshot["model"] == "qwen2.5:7b"
    assert snapshot["url"] == "http://localhost:11434"


def test_main_status_bar_exposes_distinct_model_and_endpoint_labels(qtbot):
    widget = MainStatusBar({"provider": "ollama", "ollama": {"model": "qwen2.5:7b", "base_url": "http://localhost:11434"}})
    qtbot.addWidget(widget)

    assert widget.lbl_llm_model.text()
    assert widget.lbl_llm_endpoint.text()
    assert widget.refresh_llm_status() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_window_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ui.main_status_bar'`

- [ ] **Step 3: Write minimal implementation**

```python
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


def llm_status_snapshot(config: dict | None = None) -> dict:
    ...


class MainStatusBar(QWidget):
    def __init__(self, config_provider, on_settings_clicked=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.on_settings_clicked = on_settings_clicked
        self._build_ui()
        self.refresh_llm_status()

    def refresh_llm_status(self) -> None:
        snapshot = llm_status_snapshot(self.config_provider())
        self.lbl_llm_model.setText(snapshot["summary"])
        self.lbl_llm_endpoint.setText(snapshot["url"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_window_status.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/main_status_bar.py ui/main_window.py tests/test_main_window_status.py
git commit -m "Extract main window status bar"
```

### Task 2: Rewire the main window to use the extracted widget

**Files:**
- Modify: `ui/main_window.py:1-280`
- Test: `tests/test_main_window_status.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_window_uses_shared_status_bar_module():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")

    assert "from ui.main_status_bar import MainStatusBar" in source
    assert "self.status_bar_widget = MainStatusBar(" in source
    assert "def _refresh_llm_status" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_window_status.py::test_main_window_uses_shared_status_bar_module -v`
Expected: FAIL because the main window still owns the inline status implementation.

- [ ] **Step 3: Write minimal implementation**

```python
from ui.main_status_bar import MainStatusBar, llm_status_snapshot


class MainWindow(QMainWindow):
    def __init__(self):
        ...
        self.status_header = MainStatusBar(lambda: LLM_CONFIG, self._open_settings)
        layout.addWidget(self.status_header)
        ...

    def _on_llm_changed(self, index):
        LLM_CONFIG["provider"] = "ollama" if index == 0 else "openai"
        self.status_header.refresh_llm_status()
        self.statusBar().showMessage(f"当前LLM提供方: {LLM_CONFIG['provider']}")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()
        self.status_header.refresh_llm_status()

    def _refresh_llm_status(self):
        self.status_header.refresh_llm_status()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_window_status.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/main_window.py tests/test_main_window_status.py
git commit -m "Move main window LLM status into shared widget"
```

### Task 3: Verify the whole app still behaves normally

**Files:**
- Verify: `ui/main_window.py`, `ui/main_status_bar.py`
- Test: `tests/`

- [ ] **Step 1: Run targeted compile checks**

Run: `python -m compileall ui\main_window.py ui\main_status_bar.py`
Expected: no syntax errors.

- [ ] **Step 2: Run the main window and UI regression tests**

Run: `pytest tests/test_main_window_status.py tests/test_ui_button_roles.py tests/test_ui_density.py`
Expected: all pass.

- [ ] **Step 3: Run the full suite**

Run: `pytest tests`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add ui/main_window.py ui/main_status_bar.py tests/test_main_window_status.py
git commit -m "Extract main window status bar"
```
