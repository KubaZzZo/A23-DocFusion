"""LLM JSON fenced block handling tests."""
import asyncio
from pathlib import Path

import llm.base as llm_base
from core.doc_commander import DocCommander
from llm.base import BaseLLM

TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True)


class FakeLLM(BaseLLM):
    def __init__(self, response: str):
        self.response = response

    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        return self.response


def test_extract_json_handles_single_line_json_fence(monkeypatch):
    monkeypatch.setattr(llm_base, "get_cached", lambda prompt, text: None)
    monkeypatch.setattr(llm_base, "set_cached", lambda prompt, text, data: None)
    client = FakeLLM('```json{"entities": []}```')

    result = asyncio.run(client.extract_json("prompt", "text"))

    assert result == {"entities": []}


def test_parse_command_handles_single_line_json_fence():
    commander = DocCommander.__new__(DocCommander)
    commander.llm = FakeLLM('```json{"action":"extract","target":"tables","params":{}}```')

    result = asyncio.run(commander.parse_command("extract tables"))

    assert result["action"] == "extract"
    assert result["target"] == "tables"


def test_doc_commander_rejects_non_docx_files():
    commander = DocCommander.__new__(DocCommander)
    txt_path = TEST_DATA_DIR / "note.txt"
    txt_path.write_text("plain text", encoding="utf-8")

    try:
        result = commander.execute(str(txt_path), {"action": "extract", "params": {}})
    finally:
        txt_path.unlink(missing_ok=True)

    assert result["success"] is False
    assert ".docx" in result["message"]
