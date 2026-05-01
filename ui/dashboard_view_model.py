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
    docs = DocumentDAO.get_all()
    entity_count = EntityDAO.count()
    type_counts = EntityDAO.count_by_type()
    cross_doc_entities = EntityDAO.get_cross_document_entities()
    templates = TemplateDAO.get_all()
    articles = CrawledArticleDAO.get_all()

    doc_type_counts = {}
    for doc in docs:
        doc_type = (doc.file_type or "unknown").lower()
        doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

    return DashboardSnapshot(
        docs=docs,
        recent_docs=docs[:20],
        parsed_count=sum(1 for doc in docs if doc.raw_text),
        entity_count=entity_count,
        type_counts=type_counts,
        cross_doc_entities=cross_doc_entities,
        template_count=len(templates),
        article_count=len(articles),
        doc_type_counts=doc_type_counts,
    )
