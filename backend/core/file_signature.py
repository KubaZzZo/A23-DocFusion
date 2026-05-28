"""Upload file signature validation."""
from pathlib import Path

from core.workflow_errors import WorkflowValidationError

ZIP_MAGIC = b"PK\x03\x04"
PDF_MAGIC = b"%PDF"
TEXT_EXTENSIONS = {".txt", ".md"}
IMAGE_MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".bmp": (b"BM",),
}


def validate_file_signature(filename: str, content: bytes) -> None:
    """Validate known binary formats by magic bytes."""
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        if _looks_binary(content):
            raise WorkflowValidationError(f"File content does not match extension: {suffix}")
        return
    if suffix == ".pdf" and content.startswith(PDF_MAGIC):
        return
    if suffix in {".docx", ".xlsx"} and content.startswith(ZIP_MAGIC):
        return
    if suffix in IMAGE_MAGIC and any(content.startswith(magic) for magic in IMAGE_MAGIC[suffix]):
        return
    raise WorkflowValidationError(f"File content does not match extension: {suffix}")


def _looks_binary(content: bytes) -> bool:
    if not content:
        return False
    sample = content[:4096]
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True
