"""Task adapter for crawler import and generation workflows."""
import asyncio
from pathlib import Path
from typing import Callable
from uuid import uuid4

from core.document_workflow import DocumentWorkflow
from core.entity_extractor import EntityExtractor
from crawler.news_spider import NewsSpider
from crawler.doc_generator import DocGenerator, _safe_filename
from db.database import CrawledArticleDAO, DocumentDAO, EntityDAO
from db.models import session_scope
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
        spider_cls=NewsSpider,
        crawled_dir: Path = CRAWLED_DIR,
        session_scope_factory=session_scope,
    ):
        self.article_dao = article_dao
        self.document_dao = document_dao
        self.entity_dao = entity_dao
        self.document_workflow_cls = document_workflow_cls
        self.entity_extractor_cls = entity_extractor_cls
        self.doc_generator = doc_generator
        self.spider_cls = spider_cls
        self.crawled_dir = Path(crawled_dir)
        self.session_scope_factory = session_scope_factory

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
        empty_content_count = 0
        extract_failed_count = 0
        zero_entity_count = 0
        extractor = self.entity_extractor_cls()
        document_workflow = self.document_workflow_cls(upload_dir=self.crawled_dir)
        spider = self.spider_cls()
        sem = asyncio.Semaphore(3)
        pending = set()

        async def _extract_one(job: dict) -> dict:
            try:
                result = await extractor.extract(job["content"])
                if result.get("parse_error"):
                    log.warning("crawler entity extraction parse error: %s - %s", job["title"], result["parse_error"])
                    return {"entity_count": 0, "status": "extract_failed", "error": result["parse_error"]}
                entities = result.get("entities", [])
                if entities:
                    self._store_article_document(job["article"], job["content"], document_workflow, entities)
                    return {"entity_count": len(entities), "status": "success"}
                self._store_article_document(job["article"], job["content"], document_workflow, [])
                return {"entity_count": 0, "status": "zero_entities"}
            except Exception as e:
                log.warning("crawler entity extraction failed: %s - %s", job["title"], e)
                return {"entity_count": 0, "status": "extract_failed", "error": str(e)}

        async def _bounded(job: dict) -> dict:
            async with sem:
                return await _extract_one(job)

        async def _drain_completed(done) -> bool:
            nonlocal entity_count, processed, empty_content_count, extract_failed_count, zero_entity_count
            for task in done:
                outcome = task.result()
                entity_count += outcome.get("entity_count", 0)
                status = outcome.get("status")
                if status == "extract_failed":
                    extract_failed_count += 1
                elif status == "zero_entities":
                    zero_entity_count += 1
                processed += 1
                progress({"current": processed, "total": total})
                if should_cancel and should_cancel():
                    return True
            return False

        async def _cancel_pending() -> dict:
            for left in pending:
                left.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            spider.close()
            return {
                "entity_count": entity_count,
                "processed": processed,
                "total": total,
                "cancelled": True,
                "empty_content_count": empty_content_count,
                "extract_failed_count": extract_failed_count,
                "zero_entity_count": zero_entity_count,
                "refetched_content_count": refetched_content_count,
            }

        refetched_content_count = 0
        for article in articles:
            if should_cancel and should_cancel():
                return await _cancel_pending()
            content, refetched = self._ensure_article_content(article, spider)
            if refetched:
                refetched_content_count += 1
            if not content:
                empty_content_count += 1
                processed += 1
                progress({"current": processed, "total": total})
                continue
            pending.add(asyncio.create_task(_bounded({
                "title": article.get("title", "article"),
                "article": article,
                "content": content,
            })))

            while len(pending) >= 3:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                if await _drain_completed(done):
                    return await _cancel_pending()

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if await _drain_completed(done):
                return await _cancel_pending()

        spider.close()
        return {
            "entity_count": entity_count,
            "processed": processed,
            "total": total,
            "cancelled": False,
            "empty_content_count": empty_content_count,
            "extract_failed_count": extract_failed_count,
            "zero_entity_count": zero_entity_count,
            "refetched_content_count": refetched_content_count,
        }

    @staticmethod
    def _ensure_article_content(article: dict, spider) -> tuple[str, bool]:
        content = (article.get("content") or "").strip()
        if content:
            return content, False
        try:
            refreshed = spider.fetch_article_detail(article)
        except Exception as e:
            log.warning("crawler content refresh failed: %s - %s", article.get("title", "article"), e)
            return "", False
        refreshed_content = (refreshed.get("content") or "").strip()
        if refreshed_content:
            article["content"] = refreshed_content
            if refreshed.get("author"):
                article["author"] = refreshed.get("author")
            if refreshed.get("publish_date"):
                article["publish_date"] = refreshed.get("publish_date")
            if refreshed.get("category"):
                article["category"] = refreshed.get("category")
            return refreshed_content, True
        return "", False

    def _store_article_document(
        self,
        article: dict,
        content: str,
        document_workflow,
        entities: list[dict] | None = None,
    ) -> int:
        title = article.get("title", "article")
        digest = uuid4().hex[:8]
        filename = f"crawled_{_safe_filename(title, 30)}_{digest}.txt"
        file_path = document_workflow.upload_dir / filename
        file_path.write_bytes(content.encode("utf-8"))
        with self.session_scope_factory() as session:
            doc = self._call_with_optional_session(
                self.document_dao.create,
                filename,
                "txt",
                str(file_path),
                session=session,
            )
            self._call_with_optional_session(self.document_dao.update_text, doc.id, content, session=session)
            if entities:
                self._call_with_optional_session(self.entity_dao.create_batch, doc.id, entities, session=session)
            return doc.id

    @staticmethod
    def _call_with_optional_session(func, *args, session=None):
        try:
            return func(*args, session=session)
        except TypeError as e:
            if "session" not in str(e):
                raise
            return func(*args)
