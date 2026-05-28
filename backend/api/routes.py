"""FastAPI路由定义"""
import io
from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import quote
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from api.auth import require_local_bearer_token
from config import MAX_UPLOAD_SIZE, OUTPUT_DIR, UPLOAD_DIR
from core.article_workflow import ArticleWorkflow
from core.batch_workflow import BatchWorkflow
from core.doc_commander import BACKUP_DIR
from core.document_workflow import DocumentWorkflow
from core.entity_workflow import EntityWorkflow
from core.statistics_workflow import StatisticsWorkflow
from core.template_workflow import TemplateWorkflow
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from db.database import DocumentDAO, FillTaskDAO


router = APIRouter(prefix="/api", dependencies=[Depends(require_local_bearer_token)])
public_router = APIRouter(prefix="/api")


@dataclass
class ApiWorkflows:
    document: DocumentWorkflow = field(default_factory=DocumentWorkflow)
    entity: EntityWorkflow = field(default_factory=EntityWorkflow)
    template: TemplateWorkflow = field(default_factory=TemplateWorkflow)
    article: ArticleWorkflow = field(default_factory=ArticleWorkflow)
    statistics: StatisticsWorkflow = field(default_factory=StatisticsWorkflow)
    batch: BatchWorkflow = field(default_factory=BatchWorkflow)


_workflows = ApiWorkflows()


def get_workflows() -> ApiWorkflows:
    return _workflows
SERVER_PATH_KEYS = {"path", "file_path", "backup_path", "template_path", "result_path", "report_path", "output_path"}
_HEADER_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f\"\\;]")
SEARCH_QUERY_MAX_LENGTH = 200
ENTITY_TYPE_MAX_LENGTH = 40
DATE_PATTERN = r"^\d{4}-\d{1,2}-\d{1,2}$"


class CommandRequest(BaseModel):
    doc_id: int
    command: str


class FillRequest(BaseModel):
    template_id: int
    document_ids: list[int] = Field(default_factory=list)


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int | None = Field(default=None, ge=1, le=200)

    @property
    def offset(self) -> int:
        return 0 if self.limit is None else (self.page - 1) * self.limit


def _raise_http_error(error: Exception):
    if isinstance(error, WorkflowNotFoundError):
        raise HTTPException(404, str(error))
    if isinstance(error, WorkflowValidationError):
        raise HTTPException(400, str(error))
    raise error


def _without_server_paths(value):
    if isinstance(value, dict):
        return {key: _without_server_paths(item) for key, item in value.items() if key not in SERVER_PATH_KEYS}
    if isinstance(value, list):
        return [_without_server_paths(item) for item in value]
    return value


def _public_document(doc: dict) -> dict:
    public = _without_server_paths(doc)
    public["download_url"] = f"/api/documents/{doc['id']}/download"
    return public


def _public_version(doc_id: int, version: dict) -> dict:
    public = _without_server_paths(version)
    public["download_url"] = f"/api/documents/{doc_id}/versions/{version['id']}/download"
    return public


def _resolve_download_path(raw_path: str | Path, allowed_root: str | Path) -> Path:
    try:
        file_path = Path(raw_path).resolve(strict=True)
        root_path = Path(allowed_root).resolve(strict=True)
    except OSError:
        raise HTTPException(404, "文件不存在")
    if not file_path.is_file():
        raise HTTPException(404, "文件不存在")
    if file_path != root_path and root_path not in file_path.parents:
        raise HTTPException(404, "文件不存在")
    return file_path


def _download_response(raw_path: str | Path, allowed_root: str | Path, filename: str) -> FileResponse:
    return FileResponse(_resolve_download_path(raw_path, allowed_root), filename=_safe_download_filename(filename))


def _safe_download_filename(filename: str | Path) -> str:
    name = Path(str(filename or "download")).name.strip()
    name = re.split(r"[\x00-\x1f\x7f]", name, maxsplit=1)[0].strip()
    name = _HEADER_UNSAFE_RE.sub("_", name)
    return name or "download"


def _attachment_headers(filename: str | Path) -> dict[str, str]:
    safe_name = _safe_download_filename(filename)
    ascii_name = safe_name.encode("ascii", errors="ignore").decode("ascii") or "download"
    encoded_name = quote(safe_name, safe="")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"}


def _validated_fill_task_payload(task: dict) -> dict:
    required = {"task_id", "status", "template_path", "entities"}
    if not isinstance(task, dict) or not required.issubset(task):
        raise HTTPException(500, "模板填写任务创建失败")
    return task


async def _read_limited_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"Upload exceeds maximum size of {MAX_UPLOAD_SIZE} bytes")
    return content


# --- 文档相关 ---

@router.get("/documents", tags=["文档管理"], summary="获取文档列表")
async def list_documents(
    q: str | None = Query(default=None, max_length=SEARCH_QUERY_MAX_LENGTH),
    pagination: PageParams = Depends(),
    workflows: ApiWorkflows = Depends(get_workflows),
):
    """获取所有已上传的文档列表"""
    docs = workflows.document.list_documents(limit=pagination.limit, offset=pagination.offset, keyword=q)
    return [_public_document(doc) for doc in docs]


@router.delete("/documents/{doc_id}", tags=["文档管理"], summary="删除文档")
async def delete_document(doc_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    """删除文档及其关联的实体数据"""
    try:
        return workflows.document.delete_document(doc_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.get("/documents/{doc_id}/download", tags=["文档管理"], summary="下载文档")
async def download_document(doc_id: int):
    """Download the current stored document file."""
    doc = DocumentDAO.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return _download_response(doc.file_path, UPLOAD_DIR, doc.filename)


@router.get("/documents/{doc_id}/versions", tags=["文档版本"], summary="获取文档版本")
async def list_document_versions(doc_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    try:
        return [_public_version(doc_id, version) for version in workflows.document.list_versions(doc_id)]
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.get("/documents/{doc_id}/versions/{version_id}/download", tags=["文档版本"], summary="下载文档版本")
async def download_document_version(doc_id: int, version_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    try:
        version = next((item for item in workflows.document.list_versions(doc_id) if int(item["id"]) == version_id), None)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)
    if not version:
        raise HTTPException(404, "Version not found")
    filename = f"document-{doc_id}-v{version['version_no']}{Path(version['file_path']).suffix}"
    return _download_response(version["file_path"], BACKUP_DIR, filename)


@router.post("/documents/{doc_id}/versions/{version_id}/rollback", tags=["文档版本"], summary="回滚文档版本")
async def rollback_document_version(doc_id: int, version_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    try:
        return workflows.document.rollback_version(doc_id, version_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/upload", tags=["文档管理"], summary="上传文档")
async def upload_document(file: UploadFile = File(...), workflows: ApiWorkflows = Depends(get_workflows)):
    """上传文档文件，支持 docx/md/xlsx/txt/pdf 格式"""
    try:
        return _public_document(workflows.document.upload_document(file.filename, await _read_limited_upload(file)))
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/parse/{doc_id}", tags=["文档管理"], summary="解析文档")
async def parse_document(doc_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    """解析已上传的文档，提取文本内容"""
    try:
        return workflows.document.parse_document(doc_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/extract/{doc_id}", tags=["实体提取"], summary="提取文档实体")
async def extract_entities(doc_id: int, force: bool = False, workflows: ApiWorkflows = Depends(get_workflows)):
    """从已解析的文档中提取结构化实体信息"""
    try:
        return await workflows.document.extract_entities(doc_id, force=force)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/batch/process", tags=["批量处理"], summary="批量解析、提取、汇总、导出")
async def process_batch(files: list[UploadFile] = File(...), workflows: ApiWorkflows = Depends(get_workflows)):
    if not files:
        raise HTTPException(400, "At least one file is required")
    payload = []
    for file in files:
        payload.append((file.filename or "upload.bin", await _read_limited_upload(file)))
    result = await run_in_threadpool(workflows.batch.process_files, payload)
    public = _without_server_paths(result)
    public["download_url"] = f"/api/batch/reports/{result['report_filename']}"
    return public


@router.get("/batch/reports/{filename}", tags=["批量处理"], summary="下载批量处理报告")
async def download_batch_report(filename: str, workflows: ApiWorkflows = Depends(get_workflows)):
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(400, "Invalid filename")
    path = workflows.batch.output_dir / safe_name
    if not path.is_file():
        raise HTTPException(404, "Report not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe_name,
    )


@router.post("/documents/command", tags=["文档管理"], summary="执行文档操作指令")
async def execute_command(req: CommandRequest, workflows: ApiWorkflows = Depends(get_workflows)):
    """使用自然语言指令操作文档"""
    try:
        result = await workflows.document.execute_command(req.doc_id, req.command)
        public = _without_server_paths(result)
        version = public.get("result", {}).get("version") if isinstance(public.get("result"), dict) else None
        if isinstance(version, dict) and version.get("id"):
            version["download_url"] = f"/api/documents/{req.doc_id}/versions/{version['id']}/download"
        return public
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 实体查询 ---

@router.get("/entities", tags=["实体提取"], summary="查询实体")
async def list_entities(
    doc_id: int = None,
    keyword: str | None = Query(default=None, max_length=SEARCH_QUERY_MAX_LENGTH),
    entity_type: str | None = Query(default=None, max_length=ENTITY_TYPE_MAX_LENGTH),
    date_from: str | None = Query(default=None, pattern=DATE_PATTERN),
    date_to: str | None = Query(default=None, pattern=DATE_PATTERN),
    pagination: PageParams = Depends(),
    workflows: ApiWorkflows = Depends(get_workflows),
):
    """查询已提取的实体，支持按文档ID或关键词过滤"""
    return workflows.entity.list_entities(
        doc_id=doc_id,
        keyword=keyword,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/entities/export", tags=["实体提取"], summary="导出实体数据")
async def export_entities(
    fmt: str = "csv",
    doc_id: int = None,
    keyword: str | None = Query(default=None, max_length=SEARCH_QUERY_MAX_LENGTH),
    entity_type: str | None = Query(default=None, max_length=ENTITY_TYPE_MAX_LENGTH),
    date_from: str | None = Query(default=None, pattern=DATE_PATTERN),
    date_to: str | None = Query(default=None, pattern=DATE_PATTERN),
    workflows: ApiWorkflows = Depends(get_workflows),
):
    """导出已提取实体，支持 CSV 和 Excel(xlsx)。"""
    try:
        export = workflows.entity.export_entities(
            fmt=fmt,
            doc_id=doc_id,
            keyword=keyword,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
        )
        return StreamingResponse(
            io.BytesIO(export.content),
            media_type=export.media_type,
            headers=_attachment_headers(export.filename),
        )
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.get("/search", tags=["搜索"], summary="全文搜索和实体筛选")
async def search(
    keyword: str = Query(default="", max_length=SEARCH_QUERY_MAX_LENGTH),
    entity_type: str | None = Query(default=None, max_length=ENTITY_TYPE_MAX_LENGTH),
    date_from: str | None = Query(default=None, pattern=DATE_PATTERN),
    date_to: str | None = Query(default=None, pattern=DATE_PATTERN),
    pagination: PageParams = Depends(),
    workflows: ApiWorkflows = Depends(get_workflows),
):
    keyword = (keyword or "").strip()
    return {
        "documents": [_public_document(doc) for doc in workflows.document.search_documents(keyword, limit=pagination.limit, offset=pagination.offset)] if keyword else [],
        "entities": workflows.entity.list_entities(
            keyword=keyword or None,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
            limit=pagination.limit,
            offset=pagination.offset,
        ),
    }


# --- 模板填写 ---

@router.post("/templates/upload", tags=["模板填写"], summary="上传模板")
async def upload_template(file: UploadFile = File(...), workflows: ApiWorkflows = Depends(get_workflows)):
    """上传模板表格文件，自动分析待填写字段"""
    try:
        return _without_server_paths(await workflows.template.upload_template(file.filename, await _read_limited_upload(file)))
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/templates/fill", tags=["模板填写"], summary="自动填写模板")
async def fill_template(
    req: FillRequest,
    background_tasks: BackgroundTasks,
    workflows: ApiWorkflows = Depends(get_workflows),
):
    """使用提取的实体数据自动填写模板，异步执行"""
    try:
        task = _validated_fill_task_payload(workflows.template.create_fill_task(req.template_id, req.document_ids))
        background_tasks.add_task(
            workflows.template.run_fill_task,
            task["task_id"],
            task["template_path"],
            task["entities"],
        )
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, "模板填写任务创建失败")
    return {"task_id": task["task_id"], "status": task["status"]}


@router.get("/templates/fill/{task_id}", tags=["模板填写"], summary="查询填写任务状态")
async def get_fill_status(task_id: int):
    """查询模板填写任务的执行状态和结果"""
    task = FillTaskDAO.get_by_id(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    response = {"task_id": task.id, "status": task.status, "accuracy": task.accuracy}
    if task.result_path:
        response["result_download_url"] = f"/api/templates/fill/{task.id}/download"
    return response


@router.get("/templates/fill/{task_id}/download", tags=["模板填写"], summary="下载填写结果")
async def download_fill_result(task_id: int):
    task = FillTaskDAO.get_by_id(task_id)
    if not task or not task.result_path:
        raise HTTPException(404, "结果不存在")
    path = _resolve_download_path(task.result_path, OUTPUT_DIR)
    return FileResponse(path, filename=_safe_download_filename(path.name))


@public_router.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """检查API服务运行状态"""
    return {"status": "ok"}


# --- 爬取文章 ---

@router.get("/articles", tags=["新闻爬虫"], summary="获取爬取文章列表")
async def list_articles(pagination: PageParams = Depends(), workflows: ApiWorkflows = Depends(get_workflows)):
    """获取所有已爬取的文章"""
    return workflows.article.list_articles(limit=pagination.limit, offset=pagination.offset)


@router.get("/articles/{article_id}", tags=["新闻爬虫"], summary="获取文章详情")
async def get_article(article_id: int, workflows: ApiWorkflows = Depends(get_workflows)):
    """获取单篇爬取文章的完整内容"""
    try:
        return workflows.article.get_article(article_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 统计 ---

@router.get("/statistics", tags=["系统"], summary="系统统计数据")
async def get_statistics(workflows: ApiWorkflows = Depends(get_workflows)):
    """获取系统各项统计数据"""
    return workflows.statistics.get_statistics()
