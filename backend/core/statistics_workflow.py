"""System statistics workflow shared by API and UI callers."""
from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO, TemplateDAO


class StatisticsWorkflow:
    def get_statistics(self) -> dict:
        return {
            "documents": DocumentDAO.count(),
            "entities": EntityDAO.count(),
            "templates": TemplateDAO.count(),
            "articles": CrawledArticleDAO.count(),
            "entity_types": EntityDAO.count_by_type(),
        }


__all__ = ["StatisticsWorkflow"]
