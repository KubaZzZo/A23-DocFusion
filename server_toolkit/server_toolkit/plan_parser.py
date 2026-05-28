"""Deterministic natural-language parser for clear L1/L2 tasks."""

from __future__ import annotations

import re
from pathlib import Path


class PlanUnresolvedError(ValueError):
    """Raised when a deterministic plan cannot be produced."""


def parse_instruction(instruction: str, inputs: list[str]) -> dict:
    text = instruction.lower()
    if not inputs and not _has_any(text, ["generate", "create"]) and not _has_any(instruction, ["生成", "创建"]):
        raise PlanUnresolvedError("PLAN_UNRESOLVED: no input files")

    if _is_format_then_convert(text, instruction):
        return _format_then_convert_plan(instruction, text, inputs)
    if _is_ocr_then_extract(text, instruction):
        return _ocr_then_extract_plan(instruction, inputs)
    if _is_merge_then_format(text, instruction):
        return _merge_then_format_plan(instruction, inputs)

    if _is_generate_request(text, instruction):
        return _generate_plan(instruction, inputs)
    if _is_format_request(text, instruction):
        return _format_plan(instruction, inputs)
    if _has_any(text, ["convert", "export"]) or _has_any(instruction, ["转成", "转换", "导出为", "杞垚", "杞崲"]):
        return _convert_plan(text, inputs)
    if _has_any(text, ["merge", "combine"]) or _has_any(instruction, ["合并", "拼接", "鍚堝苟"]):
        return _merge_plan(inputs)
    if _has_any(text, ["extract", "recognize"]) or _has_any(instruction, ["提取", "抽取", "识别", "鎻愬彇"]):
        return _extract_plan(instruction, inputs)
    if _has_any(text, ["analyze", "summarize table"]) or _has_any(instruction, ["分析", "统计", "汇总"]):
        return _single_step_plan("analyze", inputs[0], "output/analysis.json", {})
    if _is_generate_request(text, instruction):
        return _generate_plan(instruction, inputs)
    raise PlanUnresolvedError("PLAN_UNRESOLVED: instruction is not a supported L1/L2 task")


def _convert_plan(text: str, inputs: list[str]) -> dict:
    source = inputs[0]
    target = "pdf" if "pdf" in text else "docx" if "word" in text or "docx" in text else "txt"
    output = f"output/{Path(source).stem}.{target}"
    return _single_step_plan("convert", source, output, {"to": target})


def _merge_plan(inputs: list[str]) -> dict:
    suffix = Path(inputs[0]).suffix.lower().lstrip(".") or "txt"
    output = f"output/merged.{suffix}"
    return {
        "level": "L1",
        "requires_agent": False,
        "inputs": inputs,
        "outputs": [output],
        "timeout_seconds": 60,
        "steps": [
            {
                "id": "step_1",
                "tool": "docfusion",
                "command": "merge",
                "args": {"inputs": inputs, "output": output},
            }
        ],
    }


def _format_then_convert_plan(instruction: str, text: str, inputs: list[str]) -> dict:
    source = inputs[0]
    stem = Path(source).stem
    target = "pdf" if "pdf" in text else "docx"
    work_file = f"work/{stem}_formatted.docx"
    output = f"output/{stem}.{target}"
    return {
        "level": "L2",
        "requires_agent": False,
        "inputs": [source],
        "outputs": [output],
        "timeout_seconds": 180,
        "steps": [
            {
                "id": "step_1",
                "tool": "docfusion",
                "command": "format-docx",
                "args": {"input": source, "output": work_file, **_read_format_args(instruction)},
            },
            {
                "id": "step_2",
                "tool": "docfusion",
                "command": "convert",
                "args": {"input": work_file, "to": target, "output": output},
            },
        ],
    }


def _ocr_then_extract_plan(instruction: str, inputs: list[str]) -> dict:
    source = inputs[0]
    work_file = f"work/{Path(source).stem}.txt"
    output = "output/entities.json"
    schema = _read_schema(instruction)
    extract_args = {"input": work_file, "output": output, "type": "text"}
    if schema:
        extract_args["schema"] = ",".join(schema)
    return {
        "level": "L2",
        "requires_agent": False,
        "inputs": [source],
        "outputs": [output],
        "timeout_seconds": 180,
        "steps": [
            {"id": "step_1", "tool": "docfusion", "command": "ocr", "args": {"input": source, "output": work_file}},
            {"id": "step_2", "tool": "docfusion", "command": "extract", "args": extract_args},
        ],
    }


def _merge_then_format_plan(instruction: str, inputs: list[str]) -> dict:
    if any(Path(path).suffix.lower() != ".docx" for path in inputs):
        raise PlanUnresolvedError("PLAN_UNRESOLVED: merge then format requires docx inputs")
    work_file = "work/merged.docx"
    output = "output/merged.docx"
    return {
        "level": "L2",
        "requires_agent": False,
        "inputs": inputs,
        "outputs": [output],
        "timeout_seconds": 180,
        "steps": [
            {"id": "step_1", "tool": "docfusion", "command": "merge", "args": {"inputs": inputs, "output": work_file}},
            {
                "id": "step_2",
                "tool": "docfusion",
                "command": "format-docx",
                "args": {"input": work_file, "output": output, **_read_format_args(instruction)},
            },
        ],
    }


def _format_plan(instruction: str, inputs: list[str]) -> dict:
    source = inputs[0]
    suffix = Path(source).suffix.lower()
    output = f"output/{Path(source).stem}_formatted.docx"
    format_args = _read_format_args(instruction)
    if suffix == ".docx":
        return _single_step_plan("format-docx", source, output, format_args)
    if suffix in {".txt", ".md"}:
        work_file = f"work/{Path(source).stem}.docx"
        return {
            "level": "L2",
            "requires_agent": False,
            "inputs": [source],
            "outputs": [output],
            "timeout_seconds": 180,
            "steps": [
                {
                    "id": "step_1",
                    "tool": "docfusion",
                    "command": "convert",
                    "args": {"input": source, "to": "docx", "output": work_file},
                },
                {
                    "id": "step_2",
                    "tool": "docfusion",
                    "command": "format-docx",
                    "args": {"input": work_file, "output": output, **format_args},
                },
            ],
        }
    raise PlanUnresolvedError("PLAN_UNRESOLVED: format task requires a docx, txt, or md input")


def _extract_plan(instruction: str, inputs: list[str]) -> dict:
    schema = _read_schema(instruction)
    args = {"type": "text"}
    if schema:
        args["schema"] = ",".join(schema)
    return _single_step_plan("extract", inputs[0], "output/extracted.json", args)


def _single_step_plan(command: str, source: str, output: str, extra_args: dict) -> dict:
    args = {"input": source, "output": output, **extra_args}
    return {
        "level": "L1",
        "requires_agent": False,
        "inputs": [source],
        "outputs": [output],
        "timeout_seconds": 60,
        "steps": [{"id": "step_1", "tool": "docfusion", "command": command, "args": args}],
    }


def _is_format_then_convert(text: str, instruction: str) -> bool:
    has_format = _is_format_request(text, instruction)
    has_convert = _has_any(text, ["convert", "pdf"]) or _has_any(instruction, ["转成", "转换", "导出为"])
    return has_format and has_convert


def _is_ocr_then_extract(text: str, instruction: str) -> bool:
    has_ocr = _has_any(text, ["ocr"]) or _has_any(instruction, ["OCR", "扫描", "识别文字"])
    has_extract = _has_any(text, ["extract"]) or _has_any(instruction, ["提取", "抽取"])
    return has_ocr and has_extract


def _is_merge_then_format(text: str, instruction: str) -> bool:
    has_merge = _has_any(text, ["merge", "combine"]) or _has_any(instruction, ["合并", "拼接"])
    has_format = _is_format_request(text, instruction)
    return has_merge and has_format


def _is_format_request(text: str, instruction: str) -> bool:
    return _has_any(text, ["format", "font", "bold", "underline", "color"]) or _has_any(
        instruction,
        ["字体", "字号", "标题", "格式", "加粗", "下划线", "颜色", "变粗", "第一行"],
    )


def _read_format_args(instruction: str) -> dict:
    args: dict[str, object] = {}
    if "SimHei" in instruction or "黑体" in instruction:
        args["heading_font"] = "SimHei"
    size_match = re.search(r"\b(1[0-9]|2[0-9]|3[0-9])\b", instruction)
    if size_match:
        args["heading_size"] = int(size_match.group(1))
    if "第一行" in instruction:
        if "加粗" in instruction or "变粗" in instruction or "bold" in instruction.lower():
            args["first_line_bold"] = True
        if "下划线" in instruction or "underline" in instruction.lower():
            args["first_line_underline"] = True
        color = _read_color(instruction)
        if color:
            args["first_line_color"] = color
    return args


def _read_color(instruction: str) -> str | None:
    text = instruction.lower()
    color_map = {
        "红": "#d93025",
        "red": "#d93025",
        "蓝": "#1a73e8",
        "blue": "#1a73e8",
        "绿": "#188038",
        "green": "#188038",
        "黑": "#000000",
        "black": "#000000",
    }
    for key, value in color_map.items():
        if key in text or key in instruction:
            return value
    match = re.search(r"#?[0-9a-fA-F]{6}", instruction)
    if match:
        value = match.group(0)
        return value if value.startswith("#") else f"#{value}"
    return None


def _read_schema(instruction: str) -> list[str]:
    text = instruction.lower()
    schema = []
    if "甲方" in instruction or "party_a" in text or "鐢叉柟" in instruction:
        schema.append("party_a")
    if "乙方" in instruction or "party_b" in text:
        schema.append("party_b")
    if "金额" in instruction or "amount" in text or "閲戦" in instruction:
        schema.append("amount")
    if "日期" in instruction or "date" in text:
        schema.append("date")
    if "vendor" in text or "销售方" in instruction:
        schema.append("vendor")
    return schema


def _is_generate_request(text: str, instruction: str) -> bool:
    return _has_any(text, ["generate", "create", "write a", "produce"]) or _has_any(
        instruction,
        ["生成", "创建", "写一份", "做一份", "出一份", "帮我写", "撰写", "编写", "起草"],
    )


def _generate_plan(instruction: str, inputs: list[str]) -> dict:
    """Build an L3 agent plan for document generation tasks."""
    output_ext = _detect_output_format(instruction)
    output = f"output/generated{output_ext}"
    stem = Path(inputs[0]).stem if inputs else "generated"
    output = f"output/{stem}{output_ext}"
    return {
        "level": "L3",
        "requires_agent": True,
        "inputs": inputs,
        "outputs": [output],
        "instruction": instruction,
        "timeout_seconds": 600,
        "steps": [
            {
                "id": "step_1",
                "tool": "docfusion",
                "command": "agent-generate",
                "args": {"instruction": instruction, "inputs": inputs, "output": output},
            }
        ],
    }


def _detect_output_format(instruction: str) -> str:
    text = instruction.lower()
    if "pdf" in text:
        return ".pdf"
    if "excel" in text or "xlsx" in text or "表格" in instruction or "汇总表" in instruction:
        return ".xlsx"
    if "txt" in text or "纯文本" in instruction:
        return ".txt"
    return ".docx"


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)
