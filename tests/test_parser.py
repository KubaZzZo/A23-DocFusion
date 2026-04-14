"""文档解析器测试"""
import pytest
from pathlib import Path
from core.document_parser import DocumentParser

TEST_DIR = Path(__file__).parent / "test_data"
TEST_DIR.mkdir(exist_ok=True)


def _create_txt(content: str) -> str:
    path = TEST_DIR / "test.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _create_md(content: str) -> str:
    path = TEST_DIR / "test.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


class TestDocumentParser:
    def test_parse_txt(self):
        path = _create_txt("这是一段测试文本。\n第二行内容。")
        result = DocumentParser.parse(path)
        assert "text" in result
        assert "测试文本" in result["text"]
        assert result["file_type"] == "txt"

    def test_parse_md(self):
        path = _create_md("# 标题\n\n这是正文内容。")
        result = DocumentParser.parse(path)
        assert "text" in result
        assert "标题" in result["text"]
        assert result["file_type"] == "md"

    def test_parse_empty_txt(self):
        path = _create_txt("")
        result = DocumentParser.parse(path)
        assert result["text"] == ""

    def test_parse_unsupported_format(self):
        path = TEST_DIR / "test.xyz"
        path.write_text("test", encoding="utf-8")
        with pytest.raises(Exception):
            DocumentParser.parse(str(path))

    def test_supported_types(self):
        assert ".txt" in DocumentParser.SUPPORTED_TYPES
        assert ".md" in DocumentParser.SUPPORTED_TYPES
        assert ".docx" in DocumentParser.SUPPORTED_TYPES
        assert ".xlsx" in DocumentParser.SUPPORTED_TYPES
        assert ".png" in DocumentParser.SUPPORTED_TYPES
        assert ".jpg" in DocumentParser.SUPPORTED_TYPES
        assert ".jpeg" in DocumentParser.SUPPORTED_TYPES
        assert ".bmp" in DocumentParser.SUPPORTED_TYPES

    def test_parse_uses_cache_for_unchanged_file(self, monkeypatch):
        path = TEST_DIR / "cache_test.txt"
        path.write_text("cache me", encoding="utf-8")
        calls = {"count": 0}

        def fake_parse_txt(p):
            calls["count"] += 1
            return p.read_text(encoding="utf-8")

        monkeypatch.setattr(DocumentParser, "_parse_txt", staticmethod(fake_parse_txt), raising=False)
        monkeypatch.setattr(DocumentParser, "_parse_docx", staticmethod(lambda p: "docx"))
        monkeypatch.setattr(DocumentParser, "_parse_xlsx", staticmethod(lambda p: "xlsx"))
        monkeypatch.setattr(DocumentParser, "_parse_pdf", staticmethod(lambda p: "pdf"))
        monkeypatch.setattr(DocumentParser, "_parse_image", staticmethod(lambda p: "img"))

        first = DocumentParser.parse(str(path))
        second = DocumentParser.parse(str(path))

        assert first["text"] == "cache me"
        assert second["text"] == "cache me"
        assert calls["count"] == 1
