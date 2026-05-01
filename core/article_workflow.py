"""Crawled article workflow shared by API and UI callers."""
from core.workflow_errors import WorkflowNotFoundError
from db.database import CrawledArticleDAO


class ArticleWorkflow:
    def list_articles(self) -> list[dict]:
        return [
            {
                "id": article.id,
                "title": article.title,
                "source": article.source,
                "author": article.author,
                "publish_date": article.publish_date,
                "category": article.category,
                "crawled_at": article.crawled_at.isoformat() if article.crawled_at else None,
            }
            for article in CrawledArticleDAO.get_all()
        ]

    def get_article(self, article_id: int) -> dict:
        article = CrawledArticleDAO.get_by_id(article_id)
        if not article:
            raise WorkflowNotFoundError("文章不存在")
        return {
            "id": article.id,
            "title": article.title,
            "source": article.source,
            "author": article.author,
            "publish_date": article.publish_date,
            "content": article.content,
            "url": article.url,
            "category": article.category,
        }


__all__ = ["ArticleWorkflow"]
