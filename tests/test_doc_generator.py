from crawler.doc_generator import DocGenerator


def test_generate_all_skips_failed_article_and_continues(monkeypatch):
    articles = [
        {"title": "bad", "content": "body"},
        {"title": "good", "content": "body"},
    ]

    def fake_docx(article):
        if article["title"] == "bad":
            raise RuntimeError("docx failed")
        return f"{article['title']}.docx"

    monkeypatch.setattr(DocGenerator, "generate_docx", staticmethod(fake_docx))
    monkeypatch.setattr(DocGenerator, "generate_txt", staticmethod(lambda article: f"{article['title']}.txt"))
    monkeypatch.setattr(DocGenerator, "generate_md", staticmethod(lambda article: f"{article['title']}.md"))
    monkeypatch.setattr(DocGenerator, "generate_xlsx", staticmethod(lambda articles: "all.xlsx"))

    paths = DocGenerator.generate_all(articles)

    assert paths["docx"] == ["good.docx"]
    assert paths["txt"] == ["good.txt"]
    assert paths["md"] == ["good.md"]
    assert paths["xlsx"] == ["all.xlsx"]
    assert paths["errors"] == [{"title": "bad", "error": "docx failed"}]
