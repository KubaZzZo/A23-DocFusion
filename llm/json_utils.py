"""Utilities for parsing and normalizing LLM JSON responses."""
import json


def strip_json_code_fence(text: str) -> str:
    """Remove common Markdown code fences from an LLM JSON response."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    if "\n" in cleaned:
        first_line, rest = cleaned.split("\n", 1)
        if first_line.strip().lower() == "json":
            return rest.strip()

    if cleaned.lower().startswith("json"):
        return cleaned[4:].lstrip()
    return cleaned


def parse_json_response(text: str) -> dict:
    """Parse an LLM response as JSON, returning a stable parse-error shape."""
    try:
        return json.loads(strip_json_code_fence(text))
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}


def normalize_entity_result(result: dict) -> dict:
    """Normalize an entity extraction result to the expected public shape."""
    if not isinstance(result, dict):
        return {"entities": [], "summary": "", "topic": "", "parse_error": True, "raw_response": result}
    if result.get("parse_error"):
        return result

    normalized_entities = []
    for entity in result.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "").strip()
        value = str(entity.get("value") or "").strip()
        if not entity_type or not value:
            continue
        try:
            confidence = float(entity.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        normalized_entities.append(
            {
                "type": entity_type,
                "value": value,
                "context": str(entity.get("context") or ""),
                "confidence": confidence,
            }
        )

    return {
        "entities": normalized_entities,
        "summary": "" if result.get("summary") is None else str(result.get("summary")),
        "topic": "" if result.get("topic") is None else str(result.get("topic")),
    }
