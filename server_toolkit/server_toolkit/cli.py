"""Command-line entry point for the server toolkit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server_toolkit.tools import run_tool
from server_toolkit.worker import execute_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docfusion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute_parser = subparsers.add_parser("execute", help="Execute a task.json plan")
    execute_parser.add_argument("task_file")
    execute_parser.add_argument("--workspace", required=True)

    copy_parser = subparsers.add_parser("copy", help="Copy a file")
    copy_parser.add_argument("input")
    copy_parser.add_argument("--output", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convert a document")
    convert_parser.add_argument("input")
    convert_parser.add_argument("--to", required=True)
    convert_parser.add_argument("--output", required=True)

    format_parser = subparsers.add_parser("format-docx", help="Format a docx file")
    format_parser.add_argument("input")
    format_parser.add_argument("--output", required=True)
    format_parser.add_argument("--heading-font")
    format_parser.add_argument("--heading-size", type=float)
    format_parser.add_argument("--body-font")
    format_parser.add_argument("--body-size", type=float)
    format_parser.add_argument("--line-spacing", type=float)
    format_parser.add_argument("--margin-top-cm", type=float)
    format_parser.add_argument("--margin-bottom-cm", type=float)
    format_parser.add_argument("--margin-left-cm", type=float)
    format_parser.add_argument("--margin-right-cm", type=float)

    extract_parser = subparsers.add_parser("extract", help="Extract text")
    extract_parser.add_argument("input")
    extract_parser.add_argument("--output", required=True)
    extract_parser.add_argument("--type", default="text")
    extract_parser.add_argument("--schema")

    merge_parser = subparsers.add_parser("merge", help="Merge files")
    merge_parser.add_argument("inputs", nargs="+")
    merge_parser.add_argument("--output", required=True)

    split_parser = subparsers.add_parser("split", help="Split a PDF")
    split_parser.add_argument("input")
    split_parser.add_argument("--pages", required=True)
    split_parser.add_argument("--output", required=True)

    fill_parser = subparsers.add_parser("fill-template", help="Fill a docx or xlsx template")
    fill_parser.add_argument("input")
    fill_parser.add_argument("--data", required=True)
    fill_parser.add_argument("--output", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate a document from JSON data")
    generate_parser.add_argument("--data", required=True)
    generate_parser.add_argument("--output", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a CSV or xlsx table")
    analyze_parser.add_argument("input")
    analyze_parser.add_argument("--output", required=True)

    ocr_parser = subparsers.add_parser("ocr", help="OCR an image")
    ocr_parser.add_argument("input")
    ocr_parser.add_argument("--output", required=True)
    ocr_parser.add_argument("--lang", default="chi_sim+eng")

    validate_parser = subparsers.add_parser("validate", help="Validate a file")
    validate_parser.add_argument("input")
    validate_parser.add_argument("--max-size", type=int)
    validate_parser.add_argument("--allowed-types")

    args = parser.parse_args(argv)
    if args.command == "execute":
        result = execute_plan(Path(args.task_file), Path(args.workspace))
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0 if result.success else 1

    tool_args = vars(args).copy()
    command = str(tool_args.pop("command"))
    result = run_tool(command, tool_args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
