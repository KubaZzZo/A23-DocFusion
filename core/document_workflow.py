"""Document workflow orchestration shared by API and UI callers."""
from pathlib import Path
from datetime import datetime

from core.document_parser import DocumentParser
from core.doc_commander import DocCommander
from core.entity_extractor import EntityExtractor
from db.database import DocumentDAO, EntityDAO
from config import UPLOAD_DIR
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError


class DocumentWorkflow:
    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

    def list_documents(self) -> list[dict]:
        docs = DocumentDAO.get_all()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "parsed": d.raw_text is not None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]

    def delete_document(self, doc_id: int) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")
        if doc.file_path:
            Path(doc.file_path).unlink(missing_ok=True)
        DocumentDAO.delete(doc_id)
        return {"message": f"文档 {doc.filename} 已删除"}

    def upload_document(self, filename: str, content: bytes) -> dict:
        suffix = Path(filename).suffix.lower()
        if suffix not in DocumentParser.SUPPORTED_TYPES:
            raise WorkflowValidationError(f"不支持的格式: {suffix}")

        save_path = self._next_upload_path(filename)
        save_path.write_bytes(content)
        doc = DocumentDAO.create(filename, suffix.lstrip("."), str(save_path))
        return {"id": doc.id, "filename": doc.filename}

    def parse_document(self, doc_id: int) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")

        result = DocumentParser.parse(doc.file_path)
        DocumentDAO.update_text(doc_id, result["text"])
        return {"doc_id": doc_id, "metadata": result["metadata"], "text_length": len(result["text"])}

    async def extract_entities(self, doc_id: int) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc or not doc.raw_text:
            raise WorkflowValidationError("文档未解析，请先调用parse接口")

        extractor = EntityExtractor()
        result = await extractor.extract(doc.raw_text)
        entities = result.get("entities", [])
        EntityDAO.create_batch(doc_id, entities)
        return {"doc_id": doc_id, "entities_count": len(entities), "summary": result.get("summary", "")}

    async def execute_command(self, doc_id: int, command: str) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")

        commander = DocCommander()
        doc_info = f"文件名: {doc.filename}, 类型: {doc.file_type}"
        parsed = await commander.parse_command(command, doc_info)
        if "error" in parsed:
            raise WorkflowValidationError(parsed["error"])
        result = commander.execute(doc.file_path, parsed)
        return {"command": parsed, "result": result}

    def _next_upload_path(self, filename: str) -> Path:
        source = Path(filename)
        suffix = source.suffix.lower()
        save_path = self.upload_dir / source.name
        if not save_path.exists():
            return save_path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.upload_dir / f"{source.stem}_{timestamp}{suffix}"


__all__ = ["DocumentWorkflow", "WorkflowNotFoundError", "WorkflowValidationError"]
