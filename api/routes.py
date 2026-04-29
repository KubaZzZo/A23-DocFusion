"""FastAPI路由定义"""
import csv
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.document_workflow import DocumentWorkflow
from core.template_workflow import TemplateWorkflow
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from db.database import DocumentDAO, EntityDAO, TemplateDAO, FillTaskDAO, CrawledArticleDAO


router = APIRouter(prefix="/api")
document_workflow = DocumentWorkflow()
template_workflow = TemplateWorkflow()


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
    if keyword:
        entities = EntityDAO.search(keyword)
    elif doc_id:
        entities = EntityDAO.get_by_document(doc_id)
    else:
        entities = EntityDAO.get_all()
    return [{"id": e.id, "type": e.entity_type, "value": e.entity_value,
             "context": e.context, "confidence": e.confidence} for e in entities]


@router.get("/entities/export", tags=["实体提取"], summary="导出实体数据")
async def export_entities(fmt: str = "csv", doc_id: int = None, keyword: str = None):
    """导出已提取实体，支持 CSV 和 Excel(xlsx)。"""
    if keyword:
        entities = EntityDAO.search(keyword)
    elif doc_id:
        entities = EntityDAO.get_by_document(doc_id)
    else:
        entities = EntityDAO.get_all()

    rows = [
        {
            "id": e.id,
            "type": e.entity_type,
            "value": e.entity_value,
            "context": e.context or "",
            "confidence": e.confidence if e.confidence is not None else "",
        }
        for e in entities
    ]

    export_format = fmt.lower()
    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["id", "type", "value", "context", "confidence"])
        writer.writeheader()
        writer.writerows(rows)
        content = buffer.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=entities.csv"},
        )

    if export_format in {"xlsx", "excel"}:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Entities"
        headers = ["id", "type", "value", "context", "confidence"]
        sheet.append(headers)
        for row in rows:
            sheet.append([row[h] for h in headers])
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=entities.xlsx"},
        )

    raise HTTPException(400, "不支持的导出格式，请使用 csv 或 xlsx")


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
    articles = CrawledArticleDAO.get_all()
    return [{"id": a.id, "title": a.title, "source": a.source, "author": a.author,
             "publish_date": a.publish_date, "category": a.category,
             "crawled_at": a.crawled_at.isoformat() if a.crawled_at else None} for a in articles]


@router.get("/articles/{article_id}", tags=["新闻爬虫"], summary="获取文章详情")
async def get_article(article_id: int):
    """获取单篇爬取文章的完整内容"""
    article = CrawledArticleDAO.get_by_id(article_id)
    if not article:
        raise HTTPException(404, "文章不存在")
    return {"id": article.id, "title": article.title, "source": article.source,
            "author": article.author, "publish_date": article.publish_date,
            "content": article.content, "url": article.url, "category": article.category}


# --- 统计 ---

@router.get("/statistics", tags=["系统"], summary="系统统计数据")
async def get_statistics():
    """获取系统各项统计数据"""
    doc_count = DocumentDAO.count()
    entity_count = EntityDAO.count()
    tpl_count = TemplateDAO.count()
    article_count = CrawledArticleDAO.count()

    type_counts = EntityDAO.count_by_type()

    return {
        "documents": doc_count,
        "entities": entity_count,
        "templates": tpl_count,
        "articles": article_count,
        "entity_types": type_counts,
    }
