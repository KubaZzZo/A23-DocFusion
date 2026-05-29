"""FastAPI路由定义"""
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from api.auth import require_local_bearer_token
from config import MAX_UPLOAD_SIZE
from core.article_workflow import ArticleWorkflow
from core.document_workflow import DocumentWorkflow
from core.entity_workflow import EntityWorkflow
from core.fusion_workflow import FusionWorkflow
from core.statistics_workflow import StatisticsWorkflow
from core.template_workflow import TemplateWorkflow
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from db.database import DocumentDAO, FillTaskDAO


router = APIRouter(prefix="/api", dependencies=[Depends(require_local_bearer_token)])
public_router = APIRouter(prefix="/api")
document_workflow = DocumentWorkflow()
entity_workflow = EntityWorkflow()
template_workflow = TemplateWorkflow()
article_workflow = ArticleWorkflow()
fusion_workflow = FusionWorkflow()
statistics_workflow = StatisticsWorkflow()


class CommandRequest(BaseModel):
    doc_id: int
    command: str


class FillRequest(BaseModel):
    template_id: int
    document_ids: list[int] = Field(default_factory=list)


class ArticlesRequest(BaseModel):
    articles: list[dict] = Field(default_factory=list)


class FusionReportRequest(BaseModel):
    rows: list[dict] | None = None


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


async def _read_limited_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"Upload exceeds maximum size of {MAX_UPLOAD_SIZE} bytes")
    return content


# --- 文档相关 ---

@router.get("/documents", tags=["文档管理"], summary="获取文档列表")
async def list_documents(pagination: PageParams = Depends()):
    """获取所有已上传的文档列表"""
    return document_workflow.list_documents(limit=pagination.limit, offset=pagination.offset)


@router.delete("/documents/{doc_id}", tags=["文档管理"], summary="删除文档")
async def delete_document(doc_id: int):
    """删除文档及其关联的实体数据"""
    try:
        return document_workflow.delete_document(doc_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.get("/documents/{doc_id}/download", tags=["文档管理"], summary="下载文档")
async def download_document(doc_id: int):
    """Download the current stored document file."""
    doc = DocumentDAO.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return FileResponse(doc.file_path, filename=doc.filename)


@router.post("/documents/upload", tags=["文档管理"], summary="上传文档")
async def upload_document(file: UploadFile = File(...)):
    """上传文档文件，支持 docx/md/xlsx/txt/pdf 格式"""
    try:
        return document_workflow.upload_document(file.filename, await _read_limited_upload(file))
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/parse/{doc_id}", tags=["文档管理"], summary="解析文档")
async def parse_document(doc_id: int):
    """解析已上传的文档，提取文本内容"""
    try:
        return document_workflow.parse_document(doc_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/extract/{doc_id}", tags=["实体提取"], summary="提取文档实体")
async def extract_entities(doc_id: int, force: bool = False):
    """从已解析的文档中提取结构化实体信息"""
    try:
        return await document_workflow.extract_entities(doc_id, force=force)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/command", tags=["文档管理"], summary="执行文档操作指令")
async def execute_command(req: CommandRequest):
    """使用自然语言指令操作文档"""
    try:
        return await document_workflow.execute_command(req.doc_id, req.command)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 实体查询 ---

@router.get("/entities", tags=["实体提取"], summary="查询实体")
async def list_entities(doc_id: int = None, keyword: str = None, pagination: PageParams = Depends()):
    """查询已提取的实体，支持按文档ID或关键词过滤"""
    return entity_workflow.list_entities(
        doc_id=doc_id,
        keyword=keyword,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/entities/export", tags=["实体提取"], summary="导出实体数据")
async def export_entities(fmt: str = "csv", doc_id: int = None, keyword: str = None):
    """导出已提取实体，支持 CSV 和 Excel(xlsx)。"""
    try:
        export = entity_workflow.export_entities(fmt=fmt, doc_id=doc_id, keyword=keyword)
        return StreamingResponse(
            io.BytesIO(export.content),
            media_type=export.media_type,
            headers={"Content-Disposition": f"attachment; filename={export.filename}"},
        )
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 模板填写 ---

@router.get("/fusion/cross-document", tags=["数据融合"], summary="查询跨文档实体关联")
async def list_cross_document_entities(min_documents: int = 2, limit: int = 100):
    return fusion_workflow.list_cross_document_entities(min_documents=min_documents, limit=limit)


@router.post("/fusion/export", tags=["数据融合"], summary="导出融合报告")
async def export_fusion_report(req: FusionReportRequest):
    export = fusion_workflow.export_report(req.rows)
    return StreamingResponse(
        io.BytesIO(export.content),
        media_type=export.media_type,
        headers={"Content-Disposition": f"attachment; filename={export.filename}"},
    )


@router.post("/templates/upload", tags=["模板填写"], summary="上传模板")
async def upload_template(file: UploadFile = File(...)):
    """上传模板表格文件，自动分析待填写字段"""
    try:
        return await template_workflow.upload_template(file.filename, await _read_limited_upload(file))
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/templates/fill", tags=["模板填写"], summary="自动填写模板")
async def fill_template(req: FillRequest, background_tasks: BackgroundTasks):
    """使用提取的实体数据自动填写模板，异步执行"""
    try:
        task = template_workflow.create_fill_task(req.template_id, req.document_ids)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)
    background_tasks.add_task(
        template_workflow.run_fill_task,
        task["task_id"],
        task["template_path"],
        task["entities"],
    )
    return {"task_id": task["task_id"], "status": task["status"]}


@router.get("/templates/fill/{task_id}", tags=["模板填写"], summary="查询填写任务状态")
async def get_fill_status(task_id: int):
    """查询模板填写任务的执行状态和结果"""
    task = FillTaskDAO.get_by_id(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return {"task_id": task.id, "status": task.status,
            "result_path": task.result_path, "accuracy": task.accuracy}


@public_router.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """检查API服务运行状态"""
    return {"status": "ok"}


# --- 爬取文章 ---

@router.get("/articles", tags=["新闻爬虫"], summary="获取爬取文章列表")
async def list_articles(pagination: PageParams = Depends()):
    """获取所有已爬取的文章"""
    return article_workflow.list_articles(limit=pagination.limit, offset=pagination.offset)


@router.get("/articles/{article_id}", tags=["新闻爬虫"], summary="获取文章详情")
async def get_article(article_id: int):
    """获取单篇爬取文章的完整内容"""
    try:
        return article_workflow.get_article(article_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/articles/store", tags=["新闻爬虫"], summary="入库爬取文章")
async def store_articles(req: ArticlesRequest):
    return article_workflow.store_articles(req.articles)


@router.post("/articles/generate-documents", tags=["新闻爬虫"], summary="生成爬取文章测试文档")
async def generate_article_documents(req: ArticlesRequest):
    return article_workflow.generate_documents(req.articles)


# --- 工作流串联 (三个模块的端到端流程) ---

class WorkflowRequest(BaseModel):
    doc_ids: list[int] = Field(default_factory=list, min_length=1)
    template_id: int | None = None
    format_instruction: str = ""
    include_fusion: bool = True
    report_description: str = ""


@router.post("/workflow/extract-and-fill", tags=["工作流"], summary="提取实体并填写模板")
async def workflow_extract_and_fill(req: WorkflowRequest):
    """Module 2+3: 从文档提取实体 → 填写模板 → 可选格式化"""
    from core.workflow_engine import run_extract_and_fill
    from db.database import DocumentDAO, TemplateDAO

    if not req.template_id:
        raise HTTPException(400, "template_id is required")
    template = TemplateDAO.get_by_id(req.template_id)
    if not template:
        raise HTTPException(404, "模板不存在")

    def get_texts(doc_id):
        return DocumentDAO.get_by_id(doc_id)

    try:
        ctx = await run_extract_and_fill(
            req.doc_ids, template.file_path, get_texts, req.format_instruction or None,
        )
        return {
            "success": True,
            "entity_count": ctx.get("entity_count", 0),
            "fill_accuracy": ctx.get("fill_accuracy", 0),
            "filled_path": ctx.get("filled_path"),
            "logs": ctx.logs,
        }
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/workflow/full-pipeline", tags=["工作流"], summary="完整三模块串联流程")
async def workflow_full_pipeline(req: WorkflowRequest):
    """Module 2 → CrossDocFusion → Module 3 → Module 1: 完整的端到端流程"""
    from core.workflow_engine import run_full_pipeline
    from db.database import DocumentDAO, TemplateDAO

    if not req.template_id:
        raise HTTPException(400, "template_id is required")
    template = TemplateDAO.get_by_id(req.template_id)
    if not template:
        raise HTTPException(404, "模板不存在")

    def get_texts(doc_id):
        return DocumentDAO.get_by_id(doc_id)

    try:
        ctx = await run_full_pipeline(
            req.doc_ids, template.file_path, get_texts,
            req.format_instruction, req.include_fusion,
        )
        cross = ctx.get("cross_doc", [])
        return {
            "success": True,
            "entity_count": ctx.get("entity_count", 0),
            "cross_document_entities": len(cross),
            "fill_accuracy": ctx.get("fill_accuracy", 0),
            "filled_path": ctx.get("filled_path"),
            "logs": ctx.logs,
        }
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/workflow/batch-process", tags=["工作流"], summary="批量处理并生成融合报告")
async def workflow_batch_process(req: WorkflowRequest):
    """多文档批量提取 → 跨文档数据融合 → 生成汇总报告(Codex CLI)"""
    from core.workflow_engine import run_batch_process_and_report
    from db.database import DocumentDAO

    def get_texts(doc_id):
        return DocumentDAO.get_by_id(doc_id)

    try:
        ctx = await run_batch_process_and_report(
            req.doc_ids, get_texts, req.report_description,
        )
        return {
            "success": True,
            "entity_count": ctx.get("entity_count", 0),
            "cross_document_entities": len(ctx.get("cross_doc", [])),
            "report_path": ctx.get("report_path"),
            "logs": ctx.logs,
        }
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 统计 ---

@router.get("/statistics", tags=["系统"], summary="系统统计数据")
async def get_statistics():
    """获取系统各项统计数据"""
    return statistics_workflow.get_statistics()
