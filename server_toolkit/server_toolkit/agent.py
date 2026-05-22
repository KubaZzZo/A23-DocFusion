"""Codex CLI L3 planning helpers."""

from __future__ import annotations


def validate_l3_plan(plan: dict) -> None:
    if plan.get("level") != "L3":
        raise ValueError("L3 plan must set level='L3'")
    if not plan.get("requires_agent"):
        raise ValueError("L3 plan must set requires_agent=true")


def build_agent_prompt(user_task: str) -> str:
    return f"""You are the DocFusion document processing agent.

Rules:
1. Work only inside /workspace.
2. Read inputs from /workspace/input.
3. Write intermediate files to /workspace/work.
4. Write final files to /workspace/output.
5. Prefer docfusion commands over custom scripts.
6. Do not install software or access paths outside /workspace.

Available commands: docfusion convert, docfusion format-docx, docfusion fill-template, docfusion merge, docfusion split, docfusion extract, docfusion analyze, docfusion generate, docfusion validate.

Task:
{user_task}
"""
