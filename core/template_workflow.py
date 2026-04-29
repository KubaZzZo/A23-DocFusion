"""Template workflow orchestration shared by API and UI callers."""
import asyncio
import json
from pathlib import Path
from datetime import datetime

from core.template_filler import TemplateFiller
from core.workflow_errors import WorkflowNotFoundError
from db.database import EntityDAO, TemplateDAO, FillTaskDAO
from config import UPLOAD_DIR
from logger import get_logger

log = get_logger("core.template_workflow")


class TemplateWorkflow:
    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

    async def upload_template(self, filename: str, content: bytes) -> dict:
        save_path = self._next_upload_path(filename)
        save_path.write_bytes(content)

        filler = TemplateFiller()
        analysis = await filler.analyze_template(str(save_path))
        tpl = TemplateDAO.create(filename, str(save_path), json.dumps(analysis, ensure_ascii=False))
        return {"id": tpl.id, "filename": tpl.filename, "fields": analysis["field_names"]}

    def create_fill_task(self, template_id: int, document_ids: list[int] | None = None) -> dict:
        tpl = TemplateDAO.get_by_id(template_id)
        if not tpl:
            raise WorkflowNotFoundError("模板不存在")

        entities = self.collect_entities(document_ids or [])
        task = FillTaskDAO.create(tpl.id)
        return {"task_id": task.id, "status": "pending", "template_path": tpl.file_path, "entities": entities}

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
        asyncio.run(self.do_fill(task_id, template_path, entities))

    def _next_upload_path(self, filename: str) -> Path:
        source = Path(filename)
        save_path = self.upload_dir / source.name
        if not save_path.exists():
            return save_path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.upload_dir / f"{source.stem}_{timestamp}{source.suffix}"


__all__ = ["TemplateWorkflow"]
