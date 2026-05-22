"""Crawler bridge for the standalone redesigned Qt UI.

The FastAPI backend exposes article listing and detail endpoints, but not a
route that starts a crawl. This module reuses the existing crawler and DAO from
the main project without modifying backend or legacy UI files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from project_paths import resolve_project_root

PROJECT_ROOT = resolve_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.news_spider import NEWS_SOURCES, NewsSpider  # noqa: E402
from db.database import CrawledArticleDAO  # noqa: E402
from db.models import init_db  # noqa: E402


ProgressCallback = Callable[[dict], None]


def news_sources() -> list[str]:
    return list(NEWS_SOURCES.keys())


def crawl_articles(sources: list[str], count: int, progress: ProgressCallback | None = None) -> dict:
    init_db()
    spider = NewsSpider()
    articles: list[dict] = []
    try:
        total_sources = max(len(sources), 1)
        for source_index, source in enumerate(sources, start=1):
            if progress:
                progress(
                    {
                        "source": source,
                        "current": 0,
                        "total": count,
                        "message": f"开始爬取 {source} ({source_index}/{total_sources})",
                    }
                )

            def on_source_progress(current: int, total: int, message: str = "", source_name: str = source) -> None:
                if progress:
                    progress(
                        {
                            "source": source_name,
                            "current": current,
                            "total": total,
                            "message": message,
                        }
                    )

            source_articles = spider.crawl(source, count, on_source_progress)
            articles.extend(source_articles)

        if progress:
            progress({"source": "全部", "current": len(articles), "total": len(articles), "message": "爬取完成"})
        return {
            "requested_sources": sources,
            "requested_per_source": count,
            "fetched": len(articles),
            "articles": articles,
        }
    finally:
        spider.close()


def crawl_and_store(sources: list[str], count: int, progress: ProgressCallback | None = None) -> dict:
    result = crawl_articles(sources, count, progress)
    articles = result.get("articles", [])
    saved = CrawledArticleDAO.create_batch(articles) if articles else []
    result["saved"] = len(saved)
    return result
