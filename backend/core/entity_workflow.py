"""Entity query and export workflow shared by API and UI callers."""
import csv
import io
from dataclasses import dataclass

from core.spreadsheet_safety import escape_formula_value
from core.workflow_errors import WorkflowValidationError
from db.database import EntityDAO


@dataclass(frozen=True)
class EntityExport:
    content: bytes
    media_type: str
    filename: str


class EntityWorkflow:
    def list_entities(
        self,
        doc_id: int | None = None,
        keyword: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        return [self._serialize_entity(entity) for entity in self._query_entities(doc_id, keyword, limit, offset)]

    def export_entities(self, fmt: str = "csv", doc_id: int | None = None, keyword: str | None = None) -> EntityExport:
        rows = [
            {
                "id": entity.id,
                "type": entity.entity_type,
                "value": entity.entity_value,
                "context": entity.context or "",
                "confidence": entity.confidence if entity.confidence is not None else "",
            }
            for entity in self._query_entities(doc_id, keyword)
        ]

        export_format = fmt.lower()
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=["id", "type", "value", "context", "confidence"])
            writer.writeheader()
            writer.writerows([self._escape_export_row(row) for row in rows])
            return EntityExport(
                content=buffer.getvalue().encode("utf-8-sig"),
                media_type="text/csv; charset=utf-8",
                filename="entities.csv",
            )

        if export_format in {"xlsx", "excel"}:
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Entities"
            headers = ["id", "type", "value", "context", "confidence"]
            sheet.append(headers)
            for row in rows:
                sheet.append([escape_formula_value(row[h]) for h in headers])
            buffer = io.BytesIO()
            workbook.save(buffer)
            return EntityExport(
                content=buffer.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="entities.xlsx",
            )

        raise WorkflowValidationError("不支持的导出格式，请使用 csv 或 xlsx")

    @staticmethod
    def _query_entities(doc_id: int | None, keyword: str | None, limit: int | None = None, offset: int = 0):
        if keyword:
            return EntityDAO.search(keyword, limit=limit, offset=offset)
        if doc_id:
            return EntityDAO.get_by_document(doc_id, limit=limit, offset=offset)
        return EntityDAO.get_all(limit=limit, offset=offset)

    @staticmethod
    def _serialize_entity(entity) -> dict:
        return {
            "id": entity.id,
            "type": entity.entity_type,
            "value": entity.entity_value,
            "context": entity.context,
            "confidence": entity.confidence,
        }

    @staticmethod
    def _escape_export_row(row: dict) -> dict:
        return {key: escape_formula_value(value) for key, value in row.items()}


__all__ = ["EntityWorkflow", "EntityExport"]
