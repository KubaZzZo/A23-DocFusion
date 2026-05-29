"""Crawled article workflow shared by API and UI callers."""
from core.workflow_errors import WorkflowNotFoundError
from db.database import CrawledArticleDAO
from crawler.doc_generator import DocGenerator


class ArticleWorkflow:
    def list_articles(self, limit: int | None = None, offset: int = 0) -> list[dict]:
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
            for article in CrawledArticleDAO.get_all(limit=limit, offset=offset)
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

    def store_articles(self, articles: list[dict]) -> dict:
        saved = CrawledArticleDAO.create_batch(articles) if articles else []
        return {"saved": len(saved), "articles": len(articles)}

    def generate_documents(self, articles: list[dict]) -> dict:
        return DocGenerator.generate_all(articles)


__all__ = ["ArticleWorkflow"]
