import json

from bs4 import BeautifulSoup

from crawler.news_spider import NewsSpider


def test_parse_36kr_detail_falls_back_to_meta_description(monkeypatch):
    html = """
    <html>
      <head>
        <meta name="description" content="36氪快讯正文内容"/>
      </head>
      <body></body>
    </html>
    """
    spider = NewsSpider()
    monkeypatch.setattr(spider, "_get_soup", lambda url: BeautifulSoup(html, "lxml"))

    result = spider._parse_36kr_detail("https://example.com/36kr")

    assert result["content"] == "36氪快讯正文内容"
    spider.close()


def test_parse_thepaper_detail_reads_next_data_content(monkeypatch):
    next_data = {
        "props": {
            "pageProps": {
                "detailData": {
                    "contentDetail": {
                        "content": "<p>第一段</p><p>第二段</p>",
                        "summary": "摘要",
                        "author": "记者甲",
                        "pubTime": "2026-05-09 17:20",
                    }
                }
            }
        }
    }
    html = f"""
    <html>
      <head><meta name="description" content="摘要"/></head>
      <body>
        <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data, ensure_ascii=False)}</script>
      </body>
    </html>
    """
    spider = NewsSpider()
    monkeypatch.setattr(spider, "_get_soup", lambda url: BeautifulSoup(html, "lxml"))

    result = spider._parse_thepaper_detail("https://example.com/thepaper")

    assert "第一段" in result["content"]
    assert "第二段" in result["content"]
    assert result["author"] == "记者甲"
    assert result["publish_date"] == "2026-05-09 17:20"
    spider.close()
