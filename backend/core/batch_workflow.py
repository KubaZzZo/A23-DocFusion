"""Batch document processing workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import OUTPUT_DIR, UPLOAD_DIR
from core.document_workflow import DocumentWorkflow
from core.entity_extractor import EntityExtractor
from db.database import EntityDAO


Extractor = Callable[[str], dict[str, Any]]


class BatchWorkflow:
    def __init__(
        self,
        upload_dir: Path = UPLOAD_DIR,
        output_dir: Path = OUTPUT_DIR,
        extractor: Extractor | None = None,
    ):
        self.document_workflow = DocumentWorkflow(upload_dir=upload_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.extractor = extractor

    def process_files(self, files: Iterable[tuple[str, bytes]]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        entity_rows: list[dict[str, Any]] = []

        for filename, content in files:
            row = {
                "doc_id": None,
                "filename": filename,
                "file_type": Path(filename).suffix.lower().lstrip("."),
                "text_length": 0,
                "entities_count": 0,
                "status": "failed",
                "error": "",
            }
            try:
                uploaded = self.document_workflow.upload_document(filename, content)
                parsed = self.document_workflow.parse_document(uploaded["id"], include_text=True)
                extraction = self._extract(parsed.get("text", ""))
                entities = extraction.get("entities", [])
                EntityDAO.create_batch(uploaded["id"], entities)

                row.update(
                    {
                        "doc_id": uploaded["id"],
                        "file_type": uploaded.get("file_type", row["file_type"]),
                        "text_length": parsed.get("text_length", 0),
                        "entities_count": len(entities),
                        "status": "completed",
                    }
                )
                for entity in entities:
                    entity_rows.append(
                        {
                            "doc_id": uploaded["id"],
                            "filename": filename,
                            "type": entity.get("type", ""),
                            "value": entity.get("value", ""),
                            "confidence": entity.get("confidence", 0),
                            "context": entity.get("context", ""),
                        }
                    )
            except Exception as exc:
                row["error"] = str(exc)
            rows.append(row)

        report_path = self._write_report(rows, entity_rows)
        succeeded = sum(1 for row in rows if row["status"] == "completed")
        return {
            "batch_id": report_path.stem,
            "total": len(rows),
            "succeeded": succeeded,
            "failed": len(rows) - succeeded,
            "entities_count": len(entity_rows),
            "documents": rows,
            "report_path": str(report_path),
            "report_filename": report_path.name,
        }

    def _extract(self, text: str) -> dict[str, Any]:
        if self.extractor:
            return self.extractor(text)
        extractor = EntityExtractor(enable_verify=False)
        try:
            return asyncio.run(extractor.extract(text, force=True))
        except Exception:
            return {"entities": EntityExtractor._extract_regex_entities(text), "summary": ""}

    def _write_report(self, rows: list[dict[str, Any]], entity_rows: list[dict[str, Any]]) -> Path:
        workbook = Workbook()
        summary = workbook.active
        summary.title = "文档汇总"
        summary.append(["文档ID", "文件名", "类型", "解析字数", "实体数", "状态", "错误"])
        for row in rows:
            summary.append(
                [
                    row["doc_id"],
                    row["filename"],
                    row["file_type"],
                    row["text_length"],
                    row["entities_count"],
                    row["status"],
                    row["error"],
                ]
            )

        details = workbook.create_sheet("实体明细")
        details.append(["文档ID", "文件名", "实体类型", "实体值", "置信度", "上下文"])
        for entity in entity_rows:
            details.append(
                [
                    entity["doc_id"],
                    entity["filename"],
                    entity["type"],
                    entity["value"],
                    entity["confidence"],
                    entity["context"],
                ]
            )

        path = self.output_dir / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.xlsx"
        workbook.save(path)
        return path
