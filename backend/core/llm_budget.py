"""LLM token budget control and text truncation utilities."""
import re
from config import LLM_BUDGET
from logger import get_logger

log = get_logger("core.budget")


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 1.5 chars for Chinese, 4 chars for English)."""
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + english_chars / 4)


def truncate_for_llm(text: str, max_tokens: int = None) -> str:
    """Truncate text to fit within token budget.

    Args:
        text: Input text to truncate
        max_tokens: Maximum tokens allowed (defaults to config value)

    Returns:
        Truncated text that fits within budget
    """
    if max_tokens is None:
        max_tokens = LLM_BUDGET.get("max_tokens_per_request", 4000)

    current_tokens = estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text

    ratio = max_tokens / current_tokens
    target_chars = int(len(text) * ratio * 0.95)

    paragraphs = text.split("\n")
    truncated = []
    char_count = 0

    for para in paragraphs:
        if char_count + len(para) > target_chars:
            remaining = target_chars - char_count
            if remaining > 50:
                truncated.append(para[:remaining] + "...")
            break
        truncated.append(para)
        char_count += len(para) + 1

    result = "\n".join(truncated)
    log.warning(
        f"Text truncated: {current_tokens} tokens → ~{estimate_tokens(result)} tokens "
        f"({len(text)} → {len(result)} chars)"
    )
    return result


def should_fallback(error: Exception) -> bool:
    """Determine if error should trigger fallback strategy."""
    if not LLM_BUDGET.get("enable_fallback", True):
        return False

    error_str = str(error).lower()

    if LLM_BUDGET.get("fallback_on_timeout", True):
        if "timeout" in error_str or "timed out" in error_str:
            return True

    if LLM_BUDGET.get("fallback_on_error", True):
        fallback_patterns = [
            "rate limit",
            "quota exceeded",
            "service unavailable",
            "connection",
            "network",
        ]
        if any(pattern in error_str for pattern in fallback_patterns):
            return True

    return False
