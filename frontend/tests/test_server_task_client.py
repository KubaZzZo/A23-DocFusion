import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server_task_client import (
    ServerTaskConfig,
    _filename_from_disposition,
    _generation_instruction,
    _generation_plan,
    _generation_suffix,
    _needs_agent_plan,
    load_server_task_config,
    save_server_task_config,
)


def test_server_task_config_round_trips_to_json_file(tmp_path):
    path = tmp_path / "server-task.json"

    save_server_task_config(ServerTaskConfig(base_url="http://example.test:8010", token="secret"), path)
    loaded = load_server_task_config(path)

    assert loaded.base_url == "http://example.test:8010"
    assert loaded.token == "secret"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "base_url": "http://example.test:8010",
        "token": "secret",
    }


def test_server_task_config_uses_defaults_for_missing_file(tmp_path):
    loaded = load_server_task_config(tmp_path / "missing.json")

    assert loaded.base_url == "https://docx.zhuoruan.xyz/toolkit"
    assert loaded.token == ""


def test_server_task_config_loads_project_defaults_before_user_overrides(tmp_path):
    defaults = tmp_path / "defaults.json"
    user = tmp_path / "user.json"
    defaults.write_text(
        json.dumps({"base_url": "http://project.example:8010", "token": ""}),
        encoding="utf-8",
    )
    user.write_text(json.dumps({"token": "local-secret"}), encoding="utf-8")

    loaded = load_server_task_config(user, defaults)

    assert loaded.base_url == "http://project.example:8010"
    assert loaded.token == "local-secret"


def test_server_task_config_accepts_utf8_sig_json(tmp_path):
    path = tmp_path / "server-task.json"
    path.write_text(
        json.dumps({"base_url": "https://example.test/toolkit", "token": "secret"}),
        encoding="utf-8-sig",
    )

    loaded = load_server_task_config(path)

    assert loaded.base_url == "https://example.test/toolkit"
    assert loaded.token == "secret"


def test_filename_from_disposition_accepts_rfc5987_utf8_filename():
    header = "attachment; filename*=utf-8''frp%E9%83%A8%E7%BD%B2%E6%96%87%E6%A1%A3_formatted.docx"

    assert _filename_from_disposition(header) == "frp部署文档_formatted.docx"


def test_submit_generation_sends_instruction_without_files(monkeypatch):
    captured = {}
    client = __import__("server_task_client").ServerTaskClient("http://example.test", "secret")

    def fake_multipart(path, fields, files):
        captured["path"] = path
        captured["fields"] = fields
        captured["files"] = files
        return object()

    monkeypatch.setattr(client, "_multipart_request", fake_multipart)
    monkeypatch.setattr(client, "_open_json", lambda request, timeout=None: {"task_id": "task_1"})

    result = client.submit_generation("生成一份采购报告")

    assert result["task_id"] == "task_1"
    assert captured["path"] == "/api/server-tasks"
    assert "instruction" not in captured["fields"]
    plan = json.loads(captured["fields"]["plan"])
    assert plan["steps"][0]["command"] == "agent-generate"
    assert plan["instruction"].startswith("generate document. User request:")
    assert "生成一份采购报告" in plan["instruction"]
    assert captured["files"] == []


def test_generation_instruction_preserves_existing_english_trigger():
    assert _generation_instruction("generate a financial report") == "generate a financial report"


def test_generation_plan_serializes_chinese_as_ascii_json():
    payload = json.dumps(_generation_plan("生成一个财务报表"), ensure_ascii=True)

    assert "\\u751f\\u6210" in payload
    assert "生成" not in payload


def test_submit_generation_can_request_pdf_markdown_or_txt(monkeypatch):
    captured = {}
    client = __import__("server_task_client").ServerTaskClient("http://example.test", "secret")

    monkeypatch.setattr(client, "_multipart_request", lambda path, fields, files: captured.setdefault("fields", fields) or object())
    monkeypatch.setattr(client, "_open_json", lambda request, timeout=None: {"task_id": "task_1"})

    client.submit_generation("generate a report", output_format="pdf")

    plan = json.loads(captured["fields"]["plan"])
    assert plan["outputs"] == ["output/generated.pdf"]
    assert "Output format: PDF" in plan["instruction"]
    assert _generation_suffix("markdown") == ".md"
    assert _generation_suffix("txt") == ".txt"


def test_submit_ocr_summary_with_file_uses_agent_plan(monkeypatch, tmp_path):
    captured = {}
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"fake")
    client = __import__("server_task_client").ServerTaskClient("http://example.test", "secret")

    def fake_multipart(path, fields, files):
        captured["path"] = path
        captured["fields"] = fields
        captured["files"] = files
        return object()

    monkeypatch.setattr(client, "_multipart_request", fake_multipart)
    monkeypatch.setattr(client, "_open_json", lambda request, timeout=None: {"task_id": "task_ocr"})

    result = client.submit_instruction("OCR扫描文字，总结文档出来", [receipt])

    assert result["task_id"] == "task_ocr"
    plan = json.loads(captured["fields"]["plan"])
    assert plan["level"] == "L3"
    assert plan["inputs"] == ["input/receipt.png"]
    assert plan["steps"][0]["args"]["instruction"].startswith("agent task. User request:")
    assert "OCR扫描文字，总结文档出来" in plan["steps"][0]["args"]["instruction"]
    assert "instruction" not in captured["fields"]
    assert captured["files"] == [receipt]


def test_needs_agent_plan_sends_all_ocr_to_codex(tmp_path):
    receipt = tmp_path / "receipt.png"

    assert _needs_agent_plan("ocr then extract amount date vendor", [receipt]) is True
    assert _needs_agent_plan("OCR扫描文字，总结文档出来", [receipt]) is True
