"""Cross-document entity fusion workflow and report export."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from core.workflow_engine import CrossDocFusionStep
from db.database import DocumentDAO, EntityDAO


@dataclass(frozen=True)
class FusionExport:
    content: bytes
    media_type: str
    filename: str


class FusionWorkflow:
    def list_cross_document_entities(self, min_documents: int = 2, limit: int = 100) -> list[dict[str, Any]]:
        rows = EntityDAO.get_cross_document_entities(min_documents=min_documents, limit=limit)
        doc_name_by_id = {doc.id: doc.filename for doc in DocumentDAO.get_all()}
        fuzzy_rows = self._fuzzy_cross_document_entities(doc_name_by_id)
        return self._merge_rows(rows, fuzzy_rows, limit=limit)

    def export_report(self, rows: list[dict[str, Any]] | None = None) -> FusionExport:
        report_rows = [self._sanitize_row(row) for row in (rows if rows is not None else self.list_cross_document_entities())]
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "跨文档实体关联"
        sheet.append(["实体类型", "实体值", "关联文档数", "出现次数", "平均置信度", "关联文档", "变体"])
        for item in report_rows:
            avg_confidence = item.get("avg_confidence", item.get("confidence"))
            sheet.append(
                [
                    item.get("type", ""),
                    item.get("value", ""),
                    item.get("doc_count", ""),
                    item.get("count", item.get("total_occurrences", "")),
                    round(float(avg_confidence), 4) if avg_confidence not in (None, "") else "",
                    "、".join(self._clean_text(doc) for doc in (item.get("documents") or []) if self._clean_text(doc)),
                    "、".join(self._clean_text(variant) for variant in (item.get("variants") or []) if self._clean_text(variant)),
                ]
            )

        summary = workbook.create_sheet("融合统计")
        documents = {doc for item in report_rows for doc in item.get("documents", [])}
        summary.append(["指标", "值"])
        summary.append(["跨文档重复实体数", len(report_rows)])
        summary.append(["涉及文档数", len(documents)])
        summary.append(["报告生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

        stream = io.BytesIO()
        workbook.save(stream)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return FusionExport(
            content=stream.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"fusion_report_{stamp}.xlsx",
        )

    @staticmethod
    def save_report(path: str | Path, rows: list[dict[str, Any]]) -> Path:
        export = FusionWorkflow().export_report(rows)
        target = Path(path)
        target.write_bytes(export.content)
        return target

    def _fuzzy_cross_document_entities(self, doc_name_by_id: dict[int, str]) -> list[dict[str, Any]]:
        all_entities = []
        for doc in DocumentDAO.get_all():
            for entity in EntityDAO.get_by_document(doc.id):
                all_entities.append(
                    {
                        "type": entity.entity_type,
                        "value": entity.entity_value,
                        "confidence": entity.confidence or 0,
                        "doc_id": entity.document_id,
                    }
                )
        clusters = CrossDocFusionStep._fuzzy_cluster(all_entities)
        rows = []
        for cluster in clusters:
            if cluster.get("doc_count", 0) < 2:
                continue
            doc_ids = cluster.get("doc_ids") or []
            confidences = [e["confidence"] for e in all_entities if e["doc_id"] in doc_ids and e["type"] == cluster["type"]]
            avg_confidence = sum(confidences) / len(confidences) if confidences else cluster.get("confidence", 0)
            rows.append(
                {
                    "type": cluster["type"],
                    "value": cluster["value"],
                    "count": cluster["total_occurrences"],
                    "doc_count": cluster["doc_count"],
                    "documents": sorted(doc_name_by_id.get(doc_id, str(doc_id)) for doc_id in doc_ids),
                    "avg_confidence": avg_confidence,
                    "variants": sorted(cluster.get("variants") or []),
                    "match": "fuzzy" if len(set(cluster.get("variants") or [])) > 1 else "exact",
                }
            )
        return rows

    @staticmethod
    def _merge_rows(exact_rows: list[dict[str, Any]], fuzzy_rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        merged: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        for row in exact_rows:
            variants = sorted(set(row.get("variants") or [row.get("value", "")]))
            key = (row.get("type", ""), tuple(variants))
            merged[key] = {**row, "variants": variants, "match": row.get("match", "exact")}
        for row in fuzzy_rows:
            variants = sorted(set(row.get("variants") or [row.get("value", "")]))
            key = (row.get("type", ""), tuple(variants))
            existing = merged.get(key)
            if not existing or row.get("doc_count", 0) > existing.get("doc_count", 0):
                merged[key] = {**row, "variants": variants}
        rows = list(merged.values())
        rows = [FusionWorkflow._sanitize_row(row) for row in rows]
        rows.sort(key=lambda item: (item.get("doc_count", 0), item.get("count", 0)), reverse=True)
        return rows[:limit]

    @staticmethod
    def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(row)
        variants = [FusionWorkflow._clean_text(value) for value in (row.get("variants") or [])]
        variants = [value for value in variants if value]
        value = FusionWorkflow._clean_text(row.get("value", ""))
        if not value and variants:
            value = variants[0]
        cleaned["value"] = value
        cleaned["variants"] = sorted(set(variants))
        cleaned["documents"] = [
            value for value in (FusionWorkflow._clean_text(doc) for doc in (row.get("documents") or [])) if value
        ]
        return cleaned

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if FusionWorkflow._is_question_mark_garbage(text):
            return ""
        return text

    @staticmethod
    def _is_question_mark_garbage(text: str) -> bool:
        compact = "".join(ch for ch in text.strip() if not ch.isspace() and ch not in {",", "，", "、", ";", "；"})
        return bool(compact) and set(compact) == {"?"}
