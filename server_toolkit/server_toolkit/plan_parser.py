"""Deterministic natural-language parser for clear L1/L2 tasks."""

from __future__ import annotations

from pathlib import Path


class PlanUnresolvedError(ValueError):
    """Raised when a deterministic plan cannot be produced."""


def parse_instruction(instruction: str, inputs: list[str]) -> dict:
    text = instruction.lower()
    if not inputs and not ("生成" in instruction or "创建" in instruction):
        raise PlanUnresolvedError("PLAN_UNRESOLVED: no input files")

    if _has_any(instruction, ["转成", "转换", "导出为"]):
        return _convert_plan(text, inputs)
    if _has_any(instruction, ["合并", "拼接"]):
        return _merge_plan(inputs)
    if _has_any(instruction, ["提取", "抽取", "识别"]):
        return _extract_plan(instruction, inputs)
    if _has_any(instruction, ["分析", "统计", "汇总"]):
        return _single_step_plan("analyze", inputs[0], "output/analysis.json", {})
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


def _extract_plan(instruction: str, inputs: list[str]) -> dict:
    schema = []
    if "甲方" in instruction:
        schema.append("party_a")
    if "乙方" in instruction:
        schema.append("party_b")
    if "金额" in instruction:
        schema.append("amount")
    if "日期" in instruction:
        schema.append("date")
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


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)
