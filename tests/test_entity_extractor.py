import asyncio

from core.entity_extractor import EntityExtractor


class MultiCallLLM:
    def __init__(self):
        self.calls = []

    async def extract_json(self, prompt: str, text: str):
        self.calls.append((prompt, text))
        if "verify" in prompt.lower() or "verified" in prompt.lower():
            return {
                "entities": [
                    {
                        "type": "phone",
                        "value": "010-12345678",
                        "context": "phone 010-12345678",
                        "confidence": 0.7,
                        "verified": True,
                    },
                    {
                        "type": "custom",
                        "value": "hallucinated",
                        "context": "",
                        "confidence": 0.4,
                        "verified": False,
                    },
                ]
            }
        if "chunk-one" in text:
            return {
                "entities": [
                    {"type": "person", "value": "Alice", "context": "Alice", "confidence": 0.9},
                    {"type": "phone", "value": "010-12345678", "context": "phone", "confidence": 0.6},
                ],
                "summary": "s1",
                "topic": "topic",
            }
        return {
            "entities": [
                {"type": "person", "value": "Alice", "context": "Alice duplicate", "confidence": 0.95},
                {"type": "custom", "value": "hallucinated", "context": "", "confidence": 0.4},
            ],
            "summary": "s2",
            "topic": "topic",
        }


def test_extract_merges_multiple_chunks_and_verifies_low_confidence_entities():
    extractor = EntityExtractor.__new__(EntityExtractor)
    extractor.llm = MultiCallLLM()
    extractor.chunker = type("Chunker", (), {"chunk": lambda self, text: ["chunk-one", "chunk-two"]})()
    extractor.enable_verify = True

    result = asyncio.run(extractor.extract("full source text with phone 010-12345678"))

    assert [entity["value"] for entity in result["entities"]] == ["Alice", "010-12345678"]
    assert result["entities"][0]["confidence"] == 0.95
    assert result["entities"][1]["confidence"] == 0.75
    assert result["summary"] == "s1 s2"
    assert len(extractor.llm.calls) == 3
