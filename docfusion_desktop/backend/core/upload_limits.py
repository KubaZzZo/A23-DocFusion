"""Shared upload size validation."""
from config import MAX_UPLOAD_SIZE
from core.workflow_errors import WorkflowValidationError


def validate_upload_size(content: bytes, max_size: int | None = None) -> None:
    """Reject uploads larger than the configured byte limit."""
    limit = MAX_UPLOAD_SIZE if max_size is None else max_size
    if len(content) > limit:
        raise WorkflowValidationError(f"Upload exceeds maximum size of {limit} bytes")
