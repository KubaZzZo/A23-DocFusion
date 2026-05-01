"""UI density and layout consistency tests."""
from pathlib import Path


def test_components_define_panel_density_helpers():
    source = Path("ui/components.py").read_text(encoding="utf-8")

    assert "def apply_panel_density" in source
    assert "def set_log_height" in source


def test_primary_panels_apply_shared_density_helper():
    for path in [
        "ui/doc_panel.py",
        "ui/extract_panel.py",
        "ui/fill_panel.py",
        "ui/crawler_panel.py",
    ]:
        source = Path(path).read_text(encoding="utf-8")
        assert "apply_panel_density(" in source, path


def test_log_areas_have_consistent_fixed_height():
    doc_panel = Path("ui/doc_panel.py").read_text(encoding="utf-8")
    crawler_panel = Path("ui/crawler_panel.py").read_text(encoding="utf-8")

    assert "set_log_height(self.txt_log)" in doc_panel
    assert "set_log_height(self.txt_log)" in crawler_panel


def test_global_table_style_is_compact_but_readable():
    source = Path("ui/styles.py").read_text(encoding="utf-8")

    assert "min-height: 26px;" in source
    assert "padding: 5px 8px;" in source
    assert "padding: 6px 8px;" in source
