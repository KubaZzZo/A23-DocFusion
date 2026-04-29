"""LLM JSON parsing and normalization tests."""
from llm.json_utils import normalize_entity_result, parse_json_response


def test_parse_json_response_handles_fenced_json():
    result = parse_json_response('```json\n{"entities": []}\n```')

    assert result == {"entities": []}


def test_parse_json_response_returns_stable_parse_error():
    result = parse_json_response("not json")

    assert result["parse_error"] is True
    assert result["raw_response"] == "not json"


def test_normalize_entity_result_filters_invalid_entities_and_defaults_fields():
    result = normalize_entity_result(
        {
            "entities": [
                {"type": "person", "value": "张三", "confidence": "0.9"},
                {"type": "", "value": "缺类型"},
                {"type": "phone", "value": ""},
                "bad",
            ],
            "summary": 123,
            "topic": None,
        }
    )

    assert result == {
        "entities": [
            {
                "type": "person",
                "value": "张三",
                "context": "",
                "confidence": 0.9,
            }
        ],
        "summary": "123",
        "topic": "",
    }
