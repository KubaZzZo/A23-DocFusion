"""News spider error handling tests."""
import pytest
from bs4 import BeautifulSoup

from crawler.news_spider import NetworkFetchError, NewsSpider


def test_crawl_source_skips_failed_article_and_continues(monkeypatch):
    spider = NewsSpider()
    monkeypatch.setattr("crawler.news_spider.time.sleep", lambda _: None)
    monkeypatch.setattr(spider, "_get_soup", lambda url: BeautifulSoup("<html></html>", "lxml"))
    progress = []

    def parse_list(soup, count):
        return [
            ("第一篇文章", "http://example.com/ok"),
            ("第二篇文章", "http://example.com/bad"),
        ]

    def parse_detail(url):
        if url.endswith("/bad"):
            raise ValueError("broken detail")
        return {"content": "正文", "author": "作者", "publish_date": "2026-04-30", "category": "测试"}

    articles = spider._crawl_source(
        "测试源",
        "http://example.com/list",
        2,
        parse_list,
        parse_detail,
        lambda current, total, message="": progress.append((current, total, message)),
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "第一篇文章"
    assert progress[-1][0] == 2
    assert "解析测试源详情失败" in progress[-1][2]
    spider.close()


def test_crawl_source_reports_list_network_failure(monkeypatch):
    spider = NewsSpider()
    progress = []

    def fail_get_soup(url):
        raise NetworkFetchError("request failed")

    monkeypatch.setattr(spider, "_get_soup", fail_get_soup)

    articles = spider._crawl_source(
        "测试源",
        "http://example.com/list",
        3,
        lambda soup, count: [],
        lambda url: {},
        lambda current, total, message="": progress.append((current, total, message)),
    )

    assert articles == []
    assert progress == [(0, 3, "爬取测试源列表失败: request failed")]
    spider.close()


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            """
            <a href="/newsDetail_forward_1">足够长的标题一</a>
            <a href="/newsDetail_forward_1">足够长的标题一重复</a>
            <a href="/newsDetail_forward_2">足够长的标题二</a>
            """,
            [
                ("足够长的标题一", "https://www.thepaper.cn//newsDetail_forward_1"),
                ("足够长的标题二", "https://www.thepaper.cn//newsDetail_forward_2"),
            ],
        )
    ],
)
def test_thepaper_list_parser_uses_fixture_html(html, expected):
    spider = NewsSpider()
    soup = BeautifulSoup(html, "lxml")

    assert spider._parse_thepaper_list(soup, 10) == expected
    spider.close()
