"""Shared UI component tests."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QProgressBar

from ui.components import EmptyState, set_busy_state

_APP = None


def _qt_app():
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def test_empty_state_exposes_consistent_title_and_detail_labels():
    _qt_app()

    state = EmptyState("暂无数据", "请先导入或提取文档")

    assert state.objectName() == "emptyState"
    assert state.title.text() == "暂无数据"
    assert state.detail.text() == "请先导入或提取文档"
    assert state.title.alignment() == state.detail.alignment()
    assert state.detail.wordWrap()


def test_empty_state_can_update_text_without_recreating_widget():
    _qt_app()
    state = EmptyState("旧标题", "旧说明")

    state.set_message("新标题", "新说明")

    assert state.title.text() == "新标题"
    assert state.detail.text() == "新说明"


def test_set_busy_state_updates_button_progress_and_optional_label():
    _qt_app()
    button = QPushButton("执行")
    progress = QProgressBar()
    label = QLabel("就绪")

    set_busy_state(button, progress, True, busy_text="处理中...", label=label, label_text="正在处理")

    assert not button.isEnabled()
    assert button.text() == "处理中..."
    assert progress.isVisible()
    assert progress.minimum() == 0
    assert progress.maximum() == 0
    assert label.text() == "正在处理"

    set_busy_state(button, progress, False, idle_text="执行")

    assert button.isEnabled()
    assert button.text() == "执行"
    assert not progress.isVisible()


def test_fill_panel_uses_shared_empty_state_and_busy_helper():
    source = Path("ui/fill_panel.py").read_text(encoding="utf-8")

    assert "from ui.components import EmptyState, set_busy_state" in source
    assert "self.empty_state = EmptyState(" in source
    assert "self.lbl_empty_hint" not in source
    assert "set_busy_state(self.btn_fill, self.progress, True" in source
    assert "set_busy_state(self.btn_fill, self.progress, False" in source


def test_dashboard_panel_uses_shared_empty_state_for_distribution_sections():
    source = Path("ui/dashboard_panel.py").read_text(encoding="utf-8")

    assert "from ui.components import EmptyState" in source
    assert 'EmptyState("暂无实体数据"' in source
    assert 'EmptyState("暂无文档类型数据"' in source
