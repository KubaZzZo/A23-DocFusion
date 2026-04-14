"""Dashboard layout regression tests."""
from pathlib import Path


def test_dashboard_layout_source_contains_scrollable_expandable_sections():
    source = Path("ui/dashboard_panel.py").read_text(encoding="utf-8")

    assert "QScrollArea()" in source
    assert "setWidgetResizable(True)" in source
    assert "self.entity_search_table.setMinimumHeight(180)" in source
    assert "self.fusion_table.setMinimumHeight(220)" in source
    assert "self.txt_entity_answer.setMinimumHeight(120)" in source
    assert "QSizePolicy.Policy.Expanding" in source
    assert "right_splitter = QSplitter(Qt.Orientation.Vertical)" in source
