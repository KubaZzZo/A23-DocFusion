"""UI button role regression tests."""
from pathlib import Path


def test_main_panels_mark_secondary_and_danger_button_roles():
    doc_panel = Path("ui/doc_panel.py").read_text(encoding="utf-8")
    extract_panel = Path("ui/extract_panel.py").read_text(encoding="utf-8")
    fill_panel = Path("ui/fill_panel.py").read_text(encoding="utf-8")
    crawler_panel = Path("ui/crawler_panel.py").read_text(encoding="utf-8")
    dashboard_panel = Path("ui/dashboard_panel.py").read_text(encoding="utf-8")

    assert "mark_secondary(self.btn_open)" in doc_panel
    assert "mark_secondary(self.btn_open)" in extract_panel
    assert "mark_secondary(self.btn_batch)" in extract_panel
    assert "mark_danger(self.btn_reextract)" in extract_panel
    assert "mark_secondary(self.btn_export_csv)" in extract_panel
    assert "mark_secondary(self.btn_export_xlsx)" in extract_panel
    assert "mark_secondary(self.btn_open_tpl)" in fill_panel
    assert "mark_secondary(self.btn_refresh)" in fill_panel
    assert "mark_secondary(self.btn_open_result)" in fill_panel
    assert "mark_secondary(self.btn_gen_docs)" in crawler_panel
    assert "mark_secondary(self.btn_import)" in crawler_panel
    assert "mark_secondary(self.btn_select_all)" in crawler_panel
    assert "mark_secondary(self.btn_deselect_all)" in crawler_panel
    assert "mark_secondary(self.btn_entity_search)" in dashboard_panel
    assert "mark_secondary(self.btn_export_fusion)" in dashboard_panel


def test_primary_workflow_buttons_keep_default_primary_role():
    doc_panel = Path("ui/doc_panel.py").read_text(encoding="utf-8")
    extract_panel = Path("ui/extract_panel.py").read_text(encoding="utf-8")
    fill_panel = Path("ui/fill_panel.py").read_text(encoding="utf-8")
    crawler_panel = Path("ui/crawler_panel.py").read_text(encoding="utf-8")

    assert "mark_secondary(self.btn_exec)" not in doc_panel
    assert "mark_secondary(self.btn_extract)" not in extract_panel
    assert "mark_secondary(self.btn_fill)" not in fill_panel
    assert "mark_secondary(self.btn_crawl)" not in crawler_panel
