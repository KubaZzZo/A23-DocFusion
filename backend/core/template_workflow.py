"""Template workflow orchestration shared by API and UI callers."""
import asyncio
import threading
import json
import shutil
from pathlib import Path
from datetime import datetime

from core.template_filler import TemplateFiller
from core.file_signature import validate_file_signature
from core.upload_limits import validate_upload_size
from core.workflow_errors import WorkflowNotFoundError
from db.database import EntityDAO, TemplateDAO, FillTaskDAO
from config import OUTPUT_DIR, UPLOAD_DIR
from utils.file_utils import FileTransaction, sanitize_upload_filename
from logger import get_logger

log = get_logger("core.template_workflow")
REVIEW_CONFIDENCE_THRESHOLD = 0.75


class TemplateWorkflow:
    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

    async def upload_template(self, filename: str, content: bytes) -> dict:
        validate_upload_size(content)
        safe_filename = sanitize_upload_filename(filename, default_stem="template")
        validate_file_signature(safe_filename, content)
        with FileTransaction() as tx:
            save_path = tx.write_bytes_unique(self.upload_dir / safe_filename, content)
            filler = TemplateFiller()
            analysis = await filler.analyze_template(str(save_path))
            tpl = TemplateDAO.create(safe_filename, str(save_path), json.dumps(analysis, ensure_ascii=False))
            tx.commit()
        return {
            "id": tpl.id,
            "filename": tpl.filename,
            "path": tpl.file_path,
            "fields": analysis["field_names"],
            "analysis": analysis,
        }

    def create_fill_task(self, template_id: int, document_ids: list[int] | None = None) -> dict:
        tpl = TemplateDAO.get_by_id(template_id)
        if not tpl:
            raise WorkflowNotFoundError("模板不存在")

        entities = self.collect_entities(document_ids or [])
        task = FillTaskDAO.create(tpl.id)
        return {"task_id": task.id, "status": "pending", "template_path": tpl.file_path, "entities": entities}

    def review_fill(self, template_id: int, document_ids: list[int] | None = None) -> dict:
        tpl = TemplateDAO.get_by_id(template_id)
        if not tpl:
            raise WorkflowNotFoundError("模板不存在")

        fields = self._template_field_names(tpl)
        entities = self.collect_entities(document_ids or [])
        suggestions = []
        for field_name in fields:
            match = self._best_entity_for_field(field_name, entities)
            confidence = match.get("confidence", 0) if match else 0
            review_required = not match or float(confidence or 0) < REVIEW_CONFIDENCE_THRESHOLD
            suggestions.append(
                {
                    "field": field_name,
                    "suggested_value": match.get("value", "") if match else "",
                    "entity_type": match.get("type", "") if match else "",
                    "confidence": confidence,
                    "review_required": review_required,
                    "status": "needs_review" if review_required else "suggested",
                }
            )
        return {"template_id": template_id, "fields": fields, "suggestions": suggestions}

    async def fill_confirmed(self, template_id: int, fill_map: dict) -> dict:
        tpl = TemplateDAO.get_by_id(template_id)
        if not tpl:
            raise WorkflowNotFoundError("模板不存在")
        try:
            analysis = json.loads(tpl.fields_json or "{}")
        except json.JSONDecodeError:
            analysis = {}
        fields = analysis.get("fields") or []
        field_names = analysis.get("field_names") or []
        if fields:
            return self._write_confirmed_fill(tpl.file_path, fields, field_names, fill_map)
        return await self.fill_confirmed_map(tpl.file_path, fill_map)

    @staticmethod
    def collect_entities(document_ids: list[int]) -> list[dict]:
        entities = []
        if document_ids:
            for doc_id in document_ids:
                source_entities = EntityDAO.get_by_document(doc_id)
                for entity in source_entities:
                    entities.append(
                        {"type": entity.entity_type, "value": entity.entity_value, "confidence": entity.confidence}
                    )
        else:
            for entity in EntityDAO.get_all():
                entities.append(
                    {"type": entity.entity_type, "value": entity.entity_value, "confidence": entity.confidence}
                )
        return entities

    @staticmethod
    def _template_field_names(template) -> list[str]:
        try:
            payload = json.loads(template.fields_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        field_names = payload.get("field_names") or []
        return [str(name) for name in field_names if str(name).strip()]

    @staticmethod
    def _best_entity_for_field(field_name: str, entities: list[dict]) -> dict | None:
        normalized = field_name.lower()
        aliases = {
            "organization": {"organization", "company", "甲方", "乙方", "客户", "供应商"},
            "amount": {"amount", "金额", "合同金额", "预算"},
            "date": {"date", "日期", "签署日期", "时间"},
            "project": {"project", "项目", "项目名称"},
        }
        candidate_types = set()
        for entity_type, names in aliases.items():
            if normalized == entity_type or field_name in names or any(name.lower() in normalized for name in names):
                candidate_types.add(entity_type)
        if not candidate_types:
            candidate_types.add(normalized)

        matches = [
            entity
            for entity in entities
            if str(entity.get("type", "")).lower() in candidate_types or normalized in str(entity.get("type", "")).lower()
        ]
        if not matches:
            matches = entities
        if not matches:
            return None
        return max(matches, key=lambda item: float(item.get("confidence") or 0))

    async def do_fill(self, task_id: int, template_path: str, entities: list[dict]):
        FillTaskDAO.update_status(task_id, "processing")
        try:
            filler = TemplateFiller()
            result = await filler.fill(template_path, entities)
            FillTaskDAO.update_status(
                task_id,
                "completed",
                result_path=result.get("output_path"),
                accuracy=result.get("accuracy"),
            )
            log.info(f"填写任务 {task_id} 完成, 准确率: {result.get('accuracy')}")
        except Exception as e:
            log.error(f"填写任务 {task_id} 失败: {e}")
            FillTaskDAO.update_status(task_id, "failed")

    def run_fill_task(self, task_id: int, template_path: str, entities: list[dict]):
        """Synchronous wrapper for FastAPI BackgroundTasks."""
        coro = self.do_fill(task_id, template_path, entities)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return

        error: list[BaseException] = []

        def runner():
            try:
                asyncio.run(coro)
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=runner, name="docfusion-template-fill", daemon=False)
        thread.start()
        thread.join()
        if error:
            raise error[0]

    async def fill_confirmed_map(self, template_path: str, fill_map: dict) -> dict:
        path = Path(template_path)
        suffix = path.suffix.lower()
        if suffix not in {".xlsx", ".docx"}:
            raise ValueError(f"不支持的模板格式: {suffix}")

        filler = TemplateFiller()
        analysis = await filler.analyze_template(template_path)
        fields = analysis.get("fields", [])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{path.stem}_filled_{timestamp}{suffix}"
        output_path = OUTPUT_DIR / output_name
        shutil.copyfile(template_path, output_path)
        output_path.chmod(0o666)

        if suffix == ".xlsx":
            filler._fill_xlsx(str(output_path), fields, fill_map)
        elif suffix == ".docx":
            filler._fill_docx(str(output_path), fields, fill_map)

        field_names = analysis.get("field_names", [])
        filled_count = sum(1 for field_name in field_names if field_name in fill_map)
        total_count = len(field_names)
        filled_cells = sum(1 for field in fields if field["field_name"] in fill_map)
        total_cells = len(fields)
        unmatched_names = [field_name for field_name in field_names if field_name not in fill_map]

        return {
            "success": True,
            "output_path": str(output_path),
            "filled": filled_count,
            "total": total_count,
            "accuracy": filled_count / total_count if total_count else 0,
            "filled_cells": filled_cells,
            "total_cells": total_cells,
            "message": f"{filled_count}/{total_count} fields matched, written to {filled_cells} cells",
            "unmatched": unmatched_names,
        }

    @staticmethod
    def _write_confirmed_fill(template_path: str, fields: list[dict], field_names: list[str], fill_map: dict) -> dict:
        path = Path(template_path)
        suffix = path.suffix.lower()
        if suffix not in {".xlsx", ".docx"}:
            raise ValueError(f"不支持的模板格式: {suffix}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{path.stem}_filled_{timestamp}{suffix}"
        output_path = OUTPUT_DIR / output_name
        shutil.copyfile(template_path, output_path)
        output_path.chmod(0o666)

        filler = TemplateFiller()
        if suffix == ".xlsx":
            filler._fill_xlsx(str(output_path), fields, fill_map)
        else:
            filler._fill_docx(str(output_path), fields, fill_map)

        filled_count = sum(1 for field_name in field_names if field_name in fill_map)
        filled_cells = sum(1 for field in fields if field["field_name"] in fill_map)
        unmatched_names = [field_name for field_name in field_names if field_name not in fill_map]
        total_count = len(field_names)
        return {
            "success": True,
            "output_path": str(output_path),
            "filled": filled_count,
            "total": total_count,
            "accuracy": filled_count / total_count if total_count else 0,
            "filled_cells": filled_cells,
            "total_cells": len(fields),
            "message": f"{filled_count}/{total_count} fields matched, written to {filled_cells} cells",
            "unmatched": unmatched_names,
        }


__all__ = ["TemplateWorkflow"]
