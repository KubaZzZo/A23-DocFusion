"""Golden test data evaluation for entity extraction and document parsing."""
import json
import pytest
from pathlib import Path

from core.entity_extractor import EntityExtractor
from core.document_parser import DocumentParser


GOLDEN_DIR = Path(__file__).parent / "golden_data"
TEST_FILES_DIR = Path(__file__).parent / "test_files"


def load_golden_cases():
    """Load golden test cases from JSON."""
    golden_file = GOLDEN_DIR / "entity_extraction_golden.json"
    if not golden_file.exists():
        return []
    with open(golden_file, encoding="utf-8") as f:
        return json.load(f)


def calculate_recall(expected: list[dict], actual: list[dict]) -> float:
    if not expected:
        return 1.0

    actual_set = {(e["type"], e["value"]) for e in actual}
    matched = 0

    for exp in expected:
        exp_pair = (exp["type"], exp["value"])
        if exp_pair in actual_set:
            matched += 1

    return matched / len(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_golden_cases(), ids=lambda c: c["input_file"])
async def test_entity_extraction_golden(case):
    """Test entity extraction against golden data (requires LLM)."""
    input_file = TEST_FILES_DIR / case["input_file"]
    assert input_file.exists(), f"Test file not found: {input_file}"

    parse_result = DocumentParser.parse(str(input_file))
    text = parse_result["text"]
    assert text, f"Empty text from {input_file}"

    extractor = EntityExtractor()
    result = await extractor.extract(text)
    actual_entities = result.get("entities", [])

    recall = calculate_recall(case["expected_entities"], actual_entities)
    min_recall = case.get("min_recall", 0.8)

    assert recall >= min_recall, (
        f"Recall {recall:.2%} below threshold {min_recall:.2%}\n"
        f"Expected: {case['expected_entities']}\n"
        f"Actual: {actual_entities}"
    )


class TestRegexEntityRecall:
    """Test regex-only extraction (no LLM needed) against golden data."""

    @pytest.mark.parametrize("case", load_golden_cases(), ids=lambda c: c["input_file"])
    def test_regex_recall(self, case):
        input_file = TEST_FILES_DIR / case["input_file"]
        assert input_file.exists()

        parse_result = DocumentParser.parse(str(input_file))
        text = parse_result["text"]

        regex_entities = EntityExtractor._extract_regex_entities(text)

        regex_types = {"phone", "email", "date", "amount", "id_number"}
        expected_regex = [e for e in case["expected_entities"] if e["type"] in regex_types]

        if not expected_regex:
            return

        recall = calculate_recall(expected_regex, regex_entities)
        assert recall >= 0.5, (
            f"Regex recall {recall:.2%} too low for regex-detectable types\n"
            f"Expected regex-detectable: {expected_regex}\n"
            f"Actual regex: {regex_entities}"
        )


@pytest.mark.parametrize("filename", ["sample.txt", "sample.md"])
def test_document_parser_formats(filename):
    """Test document parser supports multiple formats."""
    file_path = TEST_FILES_DIR / filename
    assert file_path.exists(), f"Test file not found: {file_path}"

    result = DocumentParser.parse(str(file_path))
    assert "text" in result, f"No text key in parse result for {filename}"
    assert result["text"], f"Empty text from {filename}"
    assert len(result["text"]) > 10, f"Text too short from {filename}"
    assert "file_type" in result
    assert "metadata" in result
