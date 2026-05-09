"""新闻爬虫核心逻辑 - 爬取公开新闻源"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
from logger import get_logger


log = get_logger("crawler.news_spider")
DETAIL_CONCURRENCY = 3


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 新闻源配置
NEWS_SOURCES = {
    "百度百家号": {
        "list_url": "https://baijiahao.baidu.com/u?app_id=1586447938468457",
        "name": "百度百家号",
    },
    "澎湃新闻": {
        "list_url": "https://www.thepaper.cn/",
        "name": "澎湃新闻",
    },
    "新浪新闻": {
        "list_url": "https://news.sina.com.cn/",
        "name": "新浪新闻",
    },
    "36氪": {
        "list_url": "https://36kr.com/newsflashes",
        "name": "36氪",
    },
}


class NewsSpiderError(Exception):
    """Base exception for crawler failures."""


class NetworkFetchError(NewsSpiderError):
    """Raised when a page cannot be fetched."""


class ListParseError(NewsSpiderError):
    """Raised when a source list page cannot be parsed."""


class ArticleParseError(NewsSpiderError):
    """Raised when one article detail page cannot be parsed."""


class NewsSpider:
    def __init__(self):
        self.client = httpx.Client(
            timeout=15,
            follow_redirects=False,
            headers={"User-Agent": random.choice(USER_AGENTS)},
        )

    def _get_soup(self, url: str) -> BeautifulSoup:
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise NetworkFetchError(f"请求失败: {url}") from e
        return BeautifulSoup(resp.text, "lxml")

    @staticmethod
    def _notify_progress(progress_cb, current: int, total: int, message: str = ""):
        if not progress_cb:
            return
        try:
            progress_cb(current, total, message)
        except TypeError:
            progress_cb(current, total)

    def crawl(self, source_name: str, count: int = 10, progress_callback=None) -> list[dict]:
        """爬取指定新闻源的文章列表"""
        dispatch = {
            "澎湃新闻": self._crawl_thepaper,
            "新浪新闻": self._crawl_sina,
            "36氪": self._crawl_36kr,
            "百度百家号": self._crawl_baidu,
        }
        fn = dispatch.get(source_name)
        if not fn:
            log.warning("不支持的新闻源: %s", source_name)
            return []
        return fn(count, progress_callback)

    def _crawl_source(
        self,
        source: str,
        list_url: str,
        count: int,
        list_parser,
        detail_parser,
        progress_cb=None,
    ) -> list[dict]:
        try:
            soup = self._get_soup(list_url)
            urls = list_parser(soup, count)
        except NetworkFetchError as e:
            msg = f"爬取{source}列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
            return []
        except Exception as e:
            msg = f"解析{source}列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
            return []

        return self._fetch_details_concurrently(source, urls, detail_parser, progress_cb)

    def _fetch_details_concurrently(self, source: str, urls: list[tuple[str, str]], detail_parser, progress_cb=None):
        indexed_articles = []
        completed = 0
        with ThreadPoolExecutor(max_workers=DETAIL_CONCURRENCY) as executor:
            futures = {
                executor.submit(detail_parser, url): (i, title, url)
                for i, (title, url) in enumerate(urls)
            }
            for future in as_completed(futures):
                i, title, url = futures[future]
                completed += 1
                try:
                    detail = future.result()
                    detail["title"] = title
                    detail["source"] = source
                    detail["url"] = url
                    indexed_articles.append((i, detail))
                    self._notify_progress(progress_cb, completed, len(urls))
                except NetworkFetchError as e:
                    msg = f"fetch detail failed: source={source}, url={url}, error={e}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, completed, len(urls), msg)
                except Exception as e:
                    error = ArticleParseError(f"{url} - {e}")
                    msg = f"parse detail failed: source={source}, error={error}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, completed, len(urls), msg)

        indexed_articles.sort(key=lambda item: item[0])
        return [article for _, article in indexed_articles]

    @staticmethod
    def _unique_links(nodes, count: int, min_title_len: int, url_builder, href_filter=None) -> list[tuple[str, str]]:
        seen = set()
        urls = []
        for a in nodes:
            href = a.get("href", "")
            if not href or href in seen:
                continue
            if href_filter and not href_filter(href):
                continue
            seen.add(href)
            title = a.get_text(strip=True)
            if title and len(title) > min_title_len:
                urls.append((title, url_builder(href)))
            if len(urls) >= count:
                break
        return urls

    # ---- 澎湃新闻 ----
    def _crawl_thepaper(self, count: int, progress_cb=None) -> list[dict]:
        return self._crawl_source(
            "澎湃新闻",
            "https://www.thepaper.cn/",
            count,
            self._parse_thepaper_list,
            self._parse_thepaper_detail,
            progress_cb,
        )

    def _parse_thepaper_list(self, soup: BeautifulSoup, count: int) -> list[tuple[str, str]]:
        links = soup.select("a[href*='newsDetail_forward']")
        return self._unique_links(
            links,
            count,
            4,
            lambda href: href if href.startswith("http") else f"https://www.thepaper.cn/{href}",
        )

    def _parse_thepaper_detail(self, url: str) -> dict:
        soup = self._get_soup(url)
        content_div = soup.select_one(".news_txt") or soup.select_one(".index_cententWrap__Jv8jk")
        content = content_div.get_text("\n", strip=True) if content_div else ""
        author_el = soup.select_one(".news_about .news_author") or soup.select_one(".ant-space-item")
        author = author_el.get_text(strip=True) if author_el else ""
        date_el = soup.select_one(".news_about .news_time") or soup.select_one("time")
        pub_date = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")
        return {"content": content, "author": author, "publish_date": pub_date, "category": "新闻"}

    # ---- 新浪新闻 ----
    def _crawl_sina(self, count: int, progress_cb=None) -> list[dict]:
        return self._crawl_source(
            "新浪新闻",
            "https://news.sina.com.cn/",
            count,
            self._parse_sina_list,
            self._parse_sina_detail,
            progress_cb,
        )

    def _parse_sina_list(self, soup: BeautifulSoup, count: int) -> list[tuple[str, str]]:
        links = soup.select("a[href*='sina.com.cn']")
        return self._unique_links(links, count, 4, lambda href: href, lambda href: "doc-" in href)

    def _parse_sina_detail(self, url: str) -> dict:
        soup = self._get_soup(url)
        content_div = soup.select_one("#artibody") or soup.select_one(".article")
        content = content_div.get_text("\n", strip=True) if content_div else ""
        author_el = soup.select_one(".show_author") or soup.select_one(".article-editor")
        author = author_el.get_text(strip=True) if author_el else ""
        date_el = soup.select_one(".date") or soup.select_one(".date-source span")
        pub_date = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")
        return {"content": content, "author": author, "publish_date": pub_date, "category": "新闻"}

    # ---- 36氪 ----
    def _crawl_36kr(self, count: int, progress_cb=None) -> list[dict]:
        return self._crawl_source(
            "36氪",
            "https://36kr.com/newsflashes",
            count,
            self._parse_36kr_list,
            self._parse_36kr_detail,
            progress_cb,
        )

    def _parse_36kr_list(self, soup: BeautifulSoup, count: int) -> list[tuple[str, str]]:
        items = soup.select("a.article-item-title") or soup.select("a[href*='/newsflashes/']")
        return self._unique_links(
            items,
            count,
            2,
            lambda href: href if href.startswith("http") else f"https://36kr.com{href}",
        )

    def _parse_36kr_detail(self, url: str) -> dict:
        soup = self._get_soup(url)
        content_div = soup.select_one(".article-content") or soup.select_one(".common-width")
        content = content_div.get_text("\n", strip=True) if content_div else ""
        author_el = soup.select_one(".article-title-author-name")
        author = author_el.get_text(strip=True) if author_el else ""
        date_el = soup.select_one(".title-icon-item time") or soup.select_one("time")
        pub_date = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")
        return {"content": content, "author": author, "publish_date": pub_date, "category": "科技"}

    # ---- 百度百家号 ----
    def _crawl_baidu(self, count: int, progress_cb=None) -> list[dict]:
        return self._crawl_source(
            "百度百家号",
            "https://baijiahao.baidu.com/u?app_id=1586447938468457",
            count,
            self._parse_baidu_list,
            self._parse_baidu_detail,
            progress_cb,
        )

    def _parse_baidu_list(self, soup: BeautifulSoup, count: int) -> list[tuple[str, str]]:
        links = soup.select("a[href*='baijiahao.baidu.com/s']")
        return self._unique_links(
            links,
            count,
            4,
            lambda href: href if href.startswith("http") else f"https://baijiahao.baidu.com{href}",
        )

    def _parse_baidu_detail(self, url: str) -> dict:
        soup = self._get_soup(url)
        content_div = soup.select_one(".index-module_articleWrap_2Zphx") or soup.select_one("article")
        content = content_div.get_text("\n", strip=True) if content_div else ""
        author_el = soup.select_one(".index-module_authorName_27dN1") or soup.select_one(".author-name")
        author = author_el.get_text(strip=True) if author_el else ""
        date_el = soup.select_one(".index-module_articleTime_25iwO") or soup.select_one("time")
        pub_date = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")
        return {"content": content, "author": author, "publish_date": pub_date, "category": "热点"}

    def close(self):
        self.client.close()
