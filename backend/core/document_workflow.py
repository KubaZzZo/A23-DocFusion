"""Document workflow orchestration shared by API and UI callers."""
from pathlib import Path
import shutil

from core.document_parser import DocumentParser
from core.doc_commander import DocCommander
from core.entity_extractor import EntityExtractor
from db.database import DocumentDAO, DocumentVersionDAO, EntityDAO
from config import UPLOAD_DIR
from core.file_signature import validate_file_signature
from core.upload_limits import validate_upload_size
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from utils.file_utils import FileTransaction, sanitize_upload_filename


class DocumentWorkflow:
    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

    def list_documents(self, limit: int | None = None, offset: int = 0, keyword: str | None = None) -> list[dict]:
        docs = DocumentDAO.search(keyword, limit=limit, offset=offset) if keyword else DocumentDAO.get_all(limit=limit, offset=offset)
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_path": d.file_path,
                "parsed": d.raw_text is not None,
                "preview": self._preview_text(d.raw_text),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]

    def search_documents(self, keyword: str, limit: int | None = None, offset: int = 0) -> list[dict]:
        return self.list_documents(limit=limit, offset=offset, keyword=keyword)

    def delete_document(self, doc_id: int) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")
        if doc.file_path:
            Path(doc.file_path).unlink(missing_ok=True)
        DocumentDAO.delete(doc_id)
        return {"message": f"文档 {doc.filename} 已删除"}

    def upload_document(self, filename: str, content: bytes) -> dict:
        validate_upload_size(content)
        safe_filename = sanitize_upload_filename(filename)
        suffix = Path(safe_filename).suffix.lower()
        if suffix not in DocumentParser.SUPPORTED_TYPES:
            raise WorkflowValidationError(f"不支持的格式: {suffix}")
        validate_file_signature(safe_filename, content)

        with FileTransaction() as tx:
            save_path = tx.write_bytes_unique(self.upload_dir / safe_filename, content)
            doc = DocumentDAO.create(safe_filename, suffix.lstrip("."), str(save_path))
            tx.commit()
        return {"id": doc.id, "filename": doc.filename, "file_type": doc.file_type, "path": doc.file_path}

    def parse_document(self, doc_id: int, include_text: bool = False) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")

        result = DocumentParser.parse(doc.file_path)
        DocumentDAO.update_text(doc_id, result["text"])
        response = {"doc_id": doc_id, "metadata": result["metadata"], "text_length": len(result["text"])}
        if include_text:
            response["text"] = result["text"]
        return response

    async def extract_entities(self, doc_id: int, force: bool = False) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc or not doc.raw_text:
            raise WorkflowValidationError("文档未解析，请先调用parse接口")

        extractor = EntityExtractor()
        result = await extractor.extract(doc.raw_text, force=force)
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
        if result.get("success") and result.get("backup_path"):
            version = DocumentVersionDAO.create(
                doc.id,
                result["backup_path"],
                note=command,
            )
            result["version"] = self._serialize_version(version)
            self.parse_document(doc_id)
        return {"command": parsed, "result": result}

    def list_versions(self, doc_id: int) -> list[dict]:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")
        return [self._serialize_version(version) for version in DocumentVersionDAO.list_by_document(doc_id)]

    def rollback_version(self, doc_id: int, version_id: int) -> dict:
        doc = DocumentDAO.get_by_id(doc_id)
        if not doc:
            raise WorkflowNotFoundError("文档不存在")
        version = DocumentVersionDAO.get_by_id(version_id)
        if not version or version.document_id != doc_id:
            raise WorkflowNotFoundError("版本不存在")
        source = Path(version.file_path)
        if not source.is_file():
            raise WorkflowNotFoundError("版本文件不存在")
        shutil.copyfile(source, doc.file_path)
        self.parse_document(doc_id)
        return {"success": True, "doc_id": doc_id, "version_id": version_id, "message": "版本已回滚"}

    @staticmethod
    def _serialize_version(version) -> dict:
        return {
            "id": version.id,
            "document_id": version.document_id,
            "version_no": version.version_no,
            "file_path": version.file_path,
            "note": version.note,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }

    @staticmethod
    def _preview_text(text: str | None, max_length: int = 160) -> str:
        if not text:
            return ""
        compact = " ".join(text.split())
        return compact[:max_length] + ("..." if len(compact) > max_length else "")


__all__ = ["DocumentWorkflow", "WorkflowNotFoundError", "WorkflowValidationError"]
