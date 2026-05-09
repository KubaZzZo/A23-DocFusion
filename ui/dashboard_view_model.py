"""Dashboard data assembly for UI rendering."""
from dataclasses import dataclass

from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO, TemplateDAO


@dataclass(frozen=True)
class DashboardSnapshot:
    docs: list
    recent_docs: list
    parsed_count: int
    entity_count: int
    type_counts: dict[str, int]
    cross_doc_entities: list[dict]
    template_count: int
    article_count: int
    doc_type_counts: dict[str, int]


def build_dashboard_snapshot() -> DashboardSnapshot:
    docs = DocumentDAO.get_recent(limit=20)
    entity_count = EntityDAO.count()
    type_counts = EntityDAO.count_by_type()
    cross_doc_entities = EntityDAO.get_cross_document_entities()

    return DashboardSnapshot(
        docs=docs,
        recent_docs=docs,
        parsed_count=DocumentDAO.count_parsed(),
        entity_count=entity_count,
        type_counts=type_counts,
        cross_doc_entities=cross_doc_entities,
        template_count=TemplateDAO.count(),
        article_count=CrawledArticleDAO.count(),
        doc_type_counts=DocumentDAO.count_by_type(),
    )
