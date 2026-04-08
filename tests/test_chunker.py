"""文本分块器测试"""
import pytest
from core.text_chunker import TextChunker


class TestTextChunker:
    def setup_method(self):
        self.chunker = TextChunker()

    def test_short_text_single_chunk(self):
        text = "这是一段短文本。"
        chunks = self.chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self):
        chunks = self.chunker.chunk("")
        assert len(chunks) <= 1

    def test_long_text_multiple_chunks(self):
        # 生成超过 CHUNK_SIZE 的文本（需要包含换行符才能分块）
        text = "\n".join(["这是一段测试文本，用于验证分块功能。"] * 500)
        chunks = self.chunker.chunk(text)
        assert len(chunks) > 1

    def test_chunks_cover_full_text(self):
        text = "段落一。\n" * 200 + "段落二。\n" * 200
        chunks = self.chunker.chunk(text)
        # 所有chunk拼接后应包含原文的关键内容
        combined = "".join(chunks)
        assert "段落一" in combined
        assert "段落二" in combined

    def test_chunk_size_limit(self):
        from config import CHUNK_SIZE
        text = "测试内容。\n" * 1000
        chunks = self.chunker.chunk(text)
        for chunk in chunks:
            # 每个chunk不应远超CHUNK_SIZE（允许一定余量）
            assert len(chunk) <= CHUNK_SIZE * 1.5
