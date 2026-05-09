from core.text_chunker import TextChunker


def test_single_long_paragraph_is_split_to_chunk_size():
    text = "x" * 5000

    chunks = TextChunker.chunk(text, chunk_size=3000, overlap=200)

    assert len(chunks) == 2
    assert all(len(chunk) <= 3000 for chunk in chunks)
    assert chunks[0] == "x" * 3000
    assert chunks[1] == "x" * 2200
