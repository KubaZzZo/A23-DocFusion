"""FastAPI路由定义"""
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.article_workflow import ArticleWorkflow
from core.document_workflow import DocumentWorkflow
from core.entity_workflow import EntityWorkflow
from core.statistics_workflow import StatisticsWorkflow
from core.template_workflow import TemplateWorkflow
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from db.database import FillTaskDAO


router = APIRouter(prefix="/api")
document_workflow = DocumentWorkflow()
entity_workflow = EntityWorkflow()
template_workflow = TemplateWorkflow()
article_workflow = ArticleWorkflow()
statistics_workflow = StatisticsWorkflow()


class CommandRequest(BaseModel):
    doc_id: int
    command: str


class FillRequest(BaseModel):
    template_id: int
    document_ids: list[int] = []


def _raise_http_error(error: Exception):
    if isinstance(error, WorkflowNotFoundError):
        raise HTTPException(404, str(error))
    if isinstance(error, WorkflowValidationError):
        raise HTTPException(400, str(error))
    raise error


# --- 文档相关 ---

@router.get("/documents", tags=["文档管理"], summary="获取文档列表")
async def list_documents():
    """获取所有已上传的文档列表"""
    return document_workflow.list_documents()


@router.delete("/documents/{doc_id}", tags=["文档管理"], summary="删除文档")
async def delete_document(doc_id: int):
    """删除文档及其关联的实体数据"""
    try:
        return document_workflow.delete_document(doc_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


@router.post("/documents/upload", tags=["文档管理"], summary="上传文档")
async def upload_document(file: UploadFile = File(...)):
    """上传文档文件，支持 docx/md/xlsx/txt/pdf 格式"""
    try:
        return document_workflow.upload_document(file.filename, await file.read())
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
async def extract_entities(doc_id: int):
    """从已解析的文档中提取结构化实体信息"""
    try:
        return await document_workflow.extract_entities(doc_id)
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
async def list_entities(doc_id: int = None, keyword: str = None):
    """查询已提取的实体，支持按文档ID或关键词过滤"""
    return entity_workflow.list_entities(doc_id=doc_id, keyword=keyword)


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

@router.post("/templates/upload", tags=["模板填写"], summary="上传模板")
async def upload_template(file: UploadFile = File(...)):
    """上传模板表格文件，自动分析待填写字段"""
    try:
        return await template_workflow.upload_template(file.filename, await file.read())
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


@router.get("/health", tags=["系统"], summary="健康检查")
async def health():
    """检查API服务运行状态"""
    return {"status": "ok"}


# --- 爬取文章 ---

@router.get("/articles", tags=["新闻爬虫"], summary="获取爬取文章列表")
async def list_articles():
    """获取所有已爬取的文章"""
    return article_workflow.list_articles()


@router.get("/articles/{article_id}", tags=["新闻爬虫"], summary="获取文章详情")
async def get_article(article_id: int):
    """获取单篇爬取文章的完整内容"""
    try:
        return article_workflow.get_article(article_id)
    except (WorkflowNotFoundError, WorkflowValidationError) as e:
        _raise_http_error(e)


# --- 统计 ---

@router.get("/statistics", tags=["系统"], summary="系统统计数据")
async def get_statistics():
    """获取系统各项统计数据"""
    return statistics_workflow.get_statistics()
