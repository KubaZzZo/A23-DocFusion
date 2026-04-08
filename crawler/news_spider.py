"""新闻爬虫核心逻辑 - 爬取公开新闻源"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
import time
from logger import get_logger


log = get_logger("crawler.news_spider")


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


class NewsSpider:
    def __init__(self):
        self.client = httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": random.choice(USER_AGENTS)},
        )

    def _get_soup(self, url: str) -> BeautifulSoup:
        resp = self.client.get(url)
        resp.raise_for_status()
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

    # ---- 澎湃新闻 ----
    def _crawl_thepaper(self, count: int, progress_cb=None) -> list[dict]:
        articles = []
        try:
            soup = self._get_soup("https://www.thepaper.cn/")
            links = soup.select("a[href*='newsDetail_forward']")
            seen = set()
            urls = []
            for a in links:
                href = a.get("href", "")
                if href and href not in seen:
                    seen.add(href)
                    title = a.get_text(strip=True)
                    if title and len(title) > 4:
                        full_url = href if href.startswith("http") else f"https://www.thepaper.cn/{href}"
                        urls.append((title, full_url))
                if len(urls) >= count:
                    break

            for i, (title, url) in enumerate(urls):
                try:
                    detail = self._parse_thepaper_detail(url)
                    detail["title"] = title
                    detail["source"] = "澎湃新闻"
                    detail["url"] = url
                    articles.append(detail)
                except Exception as e:
                    msg = f"爬取澎湃新闻详情失败: {url} - {e}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, i + 1, len(urls), msg)
                else:
                    self._notify_progress(progress_cb, i + 1, len(urls))
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            msg = f"爬取澎湃新闻列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
        return articles

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
        articles = []
        try:
            soup = self._get_soup("https://news.sina.com.cn/")
            links = soup.select("a[href*='sina.com.cn']")
            seen = set()
            urls = []
            for a in links:
                href = a.get("href", "")
                if href and "doc-" in href and href not in seen:
                    seen.add(href)
                    title = a.get_text(strip=True)
                    if title and len(title) > 4:
                        urls.append((title, href))
                if len(urls) >= count:
                    break

            for i, (title, url) in enumerate(urls):
                try:
                    detail = self._parse_sina_detail(url)
                    detail["title"] = title
                    detail["source"] = "新浪新闻"
                    detail["url"] = url
                    articles.append(detail)
                except Exception as e:
                    msg = f"爬取新浪新闻详情失败: {url} - {e}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, i + 1, len(urls), msg)
                else:
                    self._notify_progress(progress_cb, i + 1, len(urls))
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            msg = f"爬取新浪新闻列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
        return articles

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
        articles = []
        try:
            soup = self._get_soup("https://36kr.com/newsflashes")
            items = soup.select("a.article-item-title") or soup.select("a[href*='/newsflashes/']")
            seen = set()
            urls = []
            for a in items:
                href = a.get("href", "")
                if href and href not in seen:
                    seen.add(href)
                    title = a.get_text(strip=True)
                    if title and len(title) > 2:
                        full_url = href if href.startswith("http") else f"https://36kr.com{href}"
                        urls.append((title, full_url))
                if len(urls) >= count:
                    break

            for i, (title, url) in enumerate(urls):
                try:
                    detail = self._parse_36kr_detail(url)
                    detail["title"] = title
                    detail["source"] = "36氪"
                    detail["url"] = url
                    articles.append(detail)
                except Exception as e:
                    msg = f"爬取36氪详情失败: {url} - {e}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, i + 1, len(urls), msg)
                else:
                    self._notify_progress(progress_cb, i + 1, len(urls))
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            msg = f"爬取36氪列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
        return articles

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
        articles = []
        try:
            soup = self._get_soup("https://baijiahao.baidu.com/u?app_id=1586447938468457")
            links = soup.select("a[href*='baijiahao.baidu.com/s']")
            seen = set()
            urls = []
            for a in links:
                href = a.get("href", "")
                if href and href not in seen:
                    seen.add(href)
                    title = a.get_text(strip=True)
                    if title and len(title) > 4:
                        full_url = href if href.startswith("http") else f"https://baijiahao.baidu.com{href}"
                        urls.append((title, full_url))
                if len(urls) >= count:
                    break

            for i, (title, url) in enumerate(urls):
                try:
                    detail = self._parse_baidu_detail(url)
                    detail["title"] = title
                    detail["source"] = "百度百家号"
                    detail["url"] = url
                    articles.append(detail)
                except Exception as e:
                    msg = f"爬取百度百家号详情失败: {url} - {e}"
                    log.warning(msg)
                    self._notify_progress(progress_cb, i + 1, len(urls), msg)
                else:
                    self._notify_progress(progress_cb, i + 1, len(urls))
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            msg = f"爬取百度百家号列表失败: {e}"
            log.warning(msg)
            self._notify_progress(progress_cb, 0, count, msg)
        return articles

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
