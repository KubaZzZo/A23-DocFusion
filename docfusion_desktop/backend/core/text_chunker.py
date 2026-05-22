"""文本分块器"""
from config import CHUNK_SIZE, CHUNK_OVERLAP


class TextChunker:
    """将长文本按段落分块，保持语义完整性"""

    @staticmethod
    def chunk(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
        if len(text) <= chunk_size:
            return [text]

        paragraphs = text.split("\n")
        chunks = []
        current_chunk = ""
        step = max(1, chunk_size - overlap)

        for para in paragraphs:
            if len(para) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                for start in range(0, len(para), step):
                    chunks.append(para[start:start + chunk_size].strip())
                current_chunk = ""
                continue

            if len(current_chunk) + len(para) + 1 > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # 保留重叠部分
                if overlap > 0 and current_chunk:
                    current_chunk = current_chunk[-overlap:] + "\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
