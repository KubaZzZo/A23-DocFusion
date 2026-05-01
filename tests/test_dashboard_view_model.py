"""Dashboard view model tests."""
from types import SimpleNamespace

from ui import dashboard_view_model


class FakeDocumentDAO:
    @staticmethod
    def get_all():
        return [
            SimpleNamespace(filename="a.docx", file_type="docx", raw_text="x"),
            SimpleNamespace(filename="b.txt", file_type="txt", raw_text=None),
        ]


class FakeEntityDAO:
    @staticmethod
    def count():
        return 7

    @staticmethod
    def count_by_type():
        return {"person": 4, "organization": 3}

    @staticmethod
    def get_cross_document_entities():
        return [{"type": "person", "value": "张三", "doc_count": 2, "count": 3}]


class FakeTemplateDAO:
    @staticmethod
    def get_all():
        return [1, 2, 3]


class FakeCrawledArticleDAO:
    @staticmethod
    def get_all():
        return [1, 2]


def test_build_dashboard_snapshot_collects_all_display_data(monkeypatch):
    monkeypatch.setattr(dashboard_view_model, "DocumentDAO", FakeDocumentDAO)
    monkeypatch.setattr(dashboard_view_model, "EntityDAO", FakeEntityDAO)
    monkeypatch.setattr(dashboard_view_model, "TemplateDAO", FakeTemplateDAO)
    monkeypatch.setattr(dashboard_view_model, "CrawledArticleDAO", FakeCrawledArticleDAO)

    snapshot = dashboard_view_model.build_dashboard_snapshot()

    assert snapshot.entity_count == 7
    assert snapshot.parsed_count == 1
    assert snapshot.type_counts == {"person": 4, "organization": 3}
    assert snapshot.template_count == 3
    assert snapshot.article_count == 2
    assert snapshot.cross_doc_entities[0]["value"] == "张三"
    assert len(snapshot.recent_docs) == 2


def test_dashboard_panel_uses_view_model_module():
    source = open("ui/dashboard_panel.py", encoding="utf-8").read()

    assert "from ui.dashboard_view_model import build_dashboard_snapshot" in source
    assert "self._render_snapshot(snapshot)" in source
