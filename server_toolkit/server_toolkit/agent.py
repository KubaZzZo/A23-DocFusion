"""Codex CLI L3 agent helpers — prompt construction, validation, and execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

AGENT_SYSTEM_PROMPT = """You are the DocFusion document processing agent working inside /workspace.

## Environment
- Input files: /workspace/input/ (read-only)
- Working directory: /workspace/work/ (for intermediate files)
- Output directory: /workspace/output/ (MUST write final files here)
- Task definition: /workspace/task.json

## Available Tools
Run `docfusion <command>` for deterministic operations:
  docfusion copy <input> <output>
  docfusion convert <input> <output> [--to pdf|docx|txt|md|csv]
  docfusion format-docx <input> <output> [--heading-font SimHei] [--heading-size 16] ...
  docfusion fill-template <input> <data.json> <output>
  docfusion merge <input1> <input2> ... <output>
  docfusion split <input> <output> --pages 1-3,5
  docfusion extract <input> <output> [--schema field_a,field_b]
  docfusion generate <data.json> <output>
  docfusion analyze <input> <output>
  docfusion ocr <input> <output> [--lang chi_sim+eng]
  docfusion validate <input> [--max-size 10485760] [--allowed-types pdf,docx]

## Python Libraries Available
- python-docx: Document, Pt, Cm, RGBColor, Inches, WD_ALIGN_PARAGRAPH
- openpyxl: load_workbook, Workbook, Font, PatternFill, Alignment
- PyMuPDF (fitz): PDF text extraction and manipulation
- pypdf: PdfReader, PdfWriter
- json, csv, pathlib, shutil

## Rules
1. Read input files before acting.
2. Write ALL output to /workspace/output/.
3. Use docfusion commands for simple operations, Python for complex ones.
4. Do NOT install software or access paths outside /workspace.
5. When setting Chinese fonts (宋体, 黑体, SimSun, SimHei) in python-docx,
   set both run.font.name AND the east-asia font attribute.
6. Print a summary of what was generated/modified when done.
"""


def validate_l3_plan(plan: dict) -> None:
    """Validate that a plan dict meets L3 requirements."""
    if plan.get("level") != "L3":
        raise ValueError("L3 plan must set level='L3'")
    if not plan.get("requires_agent"):
        raise ValueError("L3 plan must set requires_agent=true")


def build_agent_prompt(user_task: str) -> str:
    """Build a constrained system prompt for Codex CLI agent execution."""
    return AGENT_SYSTEM_PROMPT + f"\n\n## Task\n{user_task}"


def build_agent_prompt_from_plan(plan: dict) -> str:
    """Build agent prompt from a TaskPlan dict, extracting the instruction."""
    instruction = plan.get("instruction", "")
    if not instruction:
        steps = plan.get("steps", [])
        instruction = json.dumps(steps, ensure_ascii=False, indent=2)
    return build_agent_prompt(instruction)


# ── Codex CLI execution ───────────────────────────────────────────

def run_codex_agent(
    workspace_path: str,
    user_task: str,
    *,
    timeout: int = 600,
    model: str | None = None,
) -> dict[str, Any]:
    """Execute an L3 task via Codex CLI inside a workspace.

    Copies the agent prompt into the workspace, runs codex exec, and
    collects any generated output files.

    Returns:
        dict with keys: success, outputs, stdout, stderr, returncode
    """
    ws = Path(workspace_path)
    output_dir = ws / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_agent_prompt(user_task)
    prompt_file = ws / "work" / "agent_prompt.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")

    codex_cmd = _build_codex_command(ws, timeout, model)

    try:
        completed = subprocess.run(
            codex_cmd,
            input=prompt,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout + 30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"Codex CLI timed out after {timeout}s",
            "outputs": _list_output_files(output_dir),
            "stdout": "",
            "stderr": "timeout",
            "returncode": -1,
        }
    except OSError as exc:
        return {
            "success": False,
            "message": f"Codex CLI not available: {exc}",
            "outputs": _list_output_files(output_dir),
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
        }

    output_files = _list_output_files(output_dir)

    return {
        "success": completed.returncode == 0,
        "message": "L3 agent completed" if completed.returncode == 0 else "L3 agent failed",
        "outputs": output_files,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-1000:],
        "returncode": completed.returncode,
    }


def run_codex_agent_with_files(
    workspace_path: str,
    user_task: str,
    input_files: list[str],
    *,
    timeout: int = 600,
    model: str | None = None,
) -> dict[str, Any]:
    """Execute an L3 task with input files pre-staged in the workspace.

    Copies input files into workspace/input/ before running Codex CLI.
    """
    ws = Path(workspace_path)
    input_dir = ws / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    staged = []
    for file_path in input_files:
        src = Path(file_path)
        if not src.exists():
            continue
        dest = input_dir / src.name
        if not dest.exists():
            shutil.copyfile(src, dest)
        staged.append(str(dest))

    return run_codex_agent(workspace_path, user_task, timeout=timeout, model=model)


# ── helpers ───────────────────────────────────────────────────────

def _build_codex_command(workspace: Path, timeout: int, model: str | None) -> list[str]:
    cmd = [
        "codex", "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-rules",
        "-s", "workspace-write",
        "-C", str(workspace),
    ]
    if model:
        cmd.extend(["-m", model])
    return cmd


def _list_output_files(output_dir: Path) -> list[str]:
    if not output_dir.exists():
        return []
    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            files.append(str(path))
    return files
