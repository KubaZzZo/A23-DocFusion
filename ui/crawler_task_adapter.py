"""Task adapter for crawler import and generation workflows."""
import asyncio
from pathlib import Path
from typing import Callable
from uuid import uuid4

from core.document_workflow import DocumentWorkflow
from core.entity_extractor import EntityExtractor
from crawler.doc_generator import DocGenerator, _safe_filename
from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO
from config import CRAWLED_DIR
from logger import get_logger

log = get_logger("ui.crawler_task_adapter")

ProgressCallback = Callable[[dict], None]
CancelCallback = Callable[[], bool]


class CrawlerTaskAdapter:
    """Runs crawler panel tasks without owning UI state."""

    def __init__(
        self,
        *,
        article_dao=CrawledArticleDAO,
        document_dao=DocumentDAO,
        entity_dao=EntityDAO,
        document_workflow_cls=DocumentWorkflow,
        entity_extractor_cls=EntityExtractor,
        doc_generator=DocGenerator,
        crawled_dir: Path = CRAWLED_DIR,
    ):
        self.article_dao = article_dao
        self.document_dao = document_dao
        self.entity_dao = entity_dao
        self.document_workflow_cls = document_workflow_cls
        self.entity_extractor_cls = entity_extractor_cls
        self.doc_generator = doc_generator
        self.crawled_dir = Path(crawled_dir)

    def generate_documents(self, articles: list[dict]) -> dict:
        return self.doc_generator.generate_all(articles)

    def import_articles(
        self,
        articles: list[dict],
        progress: ProgressCallback,
        should_cancel: CancelCallback | None = None,
    ) -> dict:
        total = len(articles)
        if articles:
            self.article_dao.create_batch(articles)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._import_articles_async(articles, progress, should_cancel, total))
        finally:
            loop.close()

    async def _import_articles_async(
        self,
        articles: list[dict],
        progress: ProgressCallback,
        should_cancel: CancelCallback | None,
        total: int,
    ) -> dict:
        entity_count = 0
        processed = 0
        extractor = self.entity_extractor_cls()
        document_workflow = self.document_workflow_cls(upload_dir=self.crawled_dir)
        sem = asyncio.Semaphore(3)
        pending = set()

        async def _extract_one(job: dict) -> int:
            try:
                result = await extractor.extract(job["content"])
                entities = result.get("entities", [])
                if entities:
                    self.entity_dao.create_batch(job["doc_id"], entities)
                    return len(entities)
            except Exception as e:
                log.warning("crawler entity extraction failed: %s - %s", job["title"], e)
            return 0

        async def _bounded(job: dict) -> int:
            async with sem:
                return await _extract_one(job)

        async def _drain_completed(done) -> bool:
            nonlocal entity_count, processed
            for task in done:
                entity_count += task.result()
                processed += 1
                progress({"current": processed, "total": total})
                if should_cancel and should_cancel():
                    return True
            return False

        async def _cancel_pending() -> dict:
            for left in pending:
                left.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            return {"entity_count": entity_count, "processed": processed, "total": total, "cancelled": True}

        for article in articles:
            if should_cancel and should_cancel():
                return await _cancel_pending()
            content = article.get("content", "")
            if not content:
                processed += 1
                progress({"current": processed, "total": total})
                continue
            doc_id = self._store_article_document(article, content, document_workflow)
            pending.add(asyncio.create_task(_bounded({
                "title": article.get("title", "article"),
                "content": content,
                "doc_id": doc_id,
            })))

            while len(pending) >= 3:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                if await _drain_completed(done):
                    return await _cancel_pending()

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if await _drain_completed(done):
                return await _cancel_pending()

        return {"entity_count": entity_count, "processed": processed, "total": total, "cancelled": False}

    def _store_article_document(self, article: dict, content: str, document_workflow) -> int:
        title = article.get("title", "article")
        digest = uuid4().hex[:8]
        filename = f"crawled_{_safe_filename(title, 30)}_{digest}.txt"
        uploaded = document_workflow.upload_document(filename, content.encode("utf-8"))
        self.document_dao.update_text(uploaded["id"], content)
        doc = self.document_dao.get_by_id(uploaded["id"])
        return doc.id
