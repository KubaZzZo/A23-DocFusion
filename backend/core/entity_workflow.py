"""Entity query and export workflow shared by API and UI callers."""
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
import re

from core.spreadsheet_safety import escape_formula_value
from core.workflow_errors import WorkflowValidationError
from db.database import DocumentDAO, EntityDAO


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
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        return [
            self._serialize_entity(entity)
            for entity in self._query_entities(doc_id, keyword, entity_type, date_from, date_to, limit, offset)
        ]

    def export_entities(
        self,
        fmt: str = "csv",
        doc_id: int | None = None,
        keyword: str | None = None,
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> EntityExport:
        rows = [
            {
                "id": entity.id,
                "type": entity.entity_type,
                "value": entity.entity_value,
                "context": entity.context or "",
                "confidence": entity.confidence if entity.confidence is not None else "",
            }
            for entity in self._query_entities(doc_id, keyword, entity_type, date_from, date_to)
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

    def relationship_graph(self, limit: int = 300) -> dict:
        documents = DocumentDAO.get_all()
        document_by_id = {doc.id: doc for doc in documents}
        entities = EntityDAO.get_all(limit=limit)
        nodes = []
        edges = []
        seen_entities = set()

        for doc in documents:
            nodes.append({"id": f"doc:{doc.id}", "kind": "document", "label": doc.filename})

        for entity in entities:
            entity_key = f"entity:{entity.entity_type}:{entity.entity_value}"
            if entity_key not in seen_entities:
                nodes.append(
                    {
                        "id": entity_key,
                        "kind": "entity",
                        "type": entity.entity_type,
                        "label": entity.entity_value,
                    }
                )
                seen_entities.add(entity_key)
            if entity.document_id in document_by_id:
                edges.append(
                    {
                        "source": f"doc:{entity.document_id}",
                        "target": entity_key,
                        "label": entity.entity_type,
                        "confidence": entity.confidence,
                    }
                )

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _query_entities(
        doc_id: int | None,
        keyword: str | None,
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ):
        needs_date_filter = bool(date_from or date_to)
        query_limit = None if needs_date_filter else limit
        query_offset = 0 if needs_date_filter else offset
        if keyword or entity_type or doc_id:
            entities = EntityDAO.search(
                keyword=keyword,
                entity_type=entity_type,
                doc_id=doc_id,
                limit=query_limit,
                offset=query_offset,
            )
        else:
            entities = EntityDAO.get_all(limit=query_limit, offset=query_offset)
        if needs_date_filter:
            entities = EntityWorkflow._filter_by_date_range(entities, date_from, date_to)
            if offset:
                entities = entities[offset:]
            if limit is not None:
                entities = entities[:limit]
        return entities

    @staticmethod
    def _filter_by_date_range(entities, date_from: str | None, date_to: str | None):
        start = EntityWorkflow._parse_boundary_date(date_from)
        end = EntityWorkflow._parse_boundary_date(date_to)
        filtered = []
        for entity in entities:
            if (entity.entity_type or "").lower() != "date":
                continue
            value_date = EntityWorkflow._parse_entity_date(entity.entity_value)
            if value_date is None:
                continue
            if start and value_date < start:
                continue
            if end and value_date > end:
                continue
            filtered.append(entity)
        return filtered

    @staticmethod
    def _parse_boundary_date(value: str | None) -> date | None:
        if not value:
            return None
        return EntityWorkflow._parse_entity_date(value)

    @staticmethod
    def _parse_entity_date(value: str | None) -> date | None:
        if not value:
            return None
        text = str(value)
        match = re.search(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", text)
        if not match:
            return None
        year, month, day = (int(part) for part in match.groups())
        try:
            return datetime(year, month, day).date()
        except ValueError:
            return None

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
