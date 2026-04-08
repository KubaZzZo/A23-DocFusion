"""FastAPI路由定义"""
import csv
import io
import json
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core import DocumentParser, EntityExtractor, DocCommander, TemplateFiller
from db.database import DocumentDAO, EntityDAO, TemplateDAO, FillTaskDAO, CrawledArticleDAO
from config import UPLOAD_DIR
from logger import get_logger

log = get_logger("api.routes")

router = APIRouter(prefix="/api")


class CommandRequest(BaseModel):
    doc_id: int
    command: str


class FillRequest(BaseModel):
    template_id: int
    document_ids: list[int] = []


# --- 文档相关 ---

@router.get("/documents", tags=["文档管理"], summary="获取文档列表")
async def list_documents():
    """获取所有已上传的文档列表"""
    docs = DocumentDAO.get_all()
    return [{"id": d.id, "filename": d.filename, "file_type": d.file_type,
             "parsed": d.raw_text is not None,
             "created_at": d.created_at.isoformat() if d.created_at else None} for d in docs]


@router.delete("/documents/{doc_id}", tags=["文档管理"], summary="删除文档")
async def delete_document(doc_id: int):
    """删除文档及其关联的实体数据"""
    doc = DocumentDAO.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    # 删除物理文件
    if doc.file_path:
        Path(doc.file_path).unlink(missing_ok=True)
    DocumentDAO.delete(doc_id)
    return {"message": f"文档 {doc.filename} 已删除"}


@router.post("/documents/upload", tags=["文档管理"], summary="上传文档")
async def upload_document(file: UploadFile = File(...)):
    """上传文档文件，支持 docx/md/xlsx/txt/pdf 格式"""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in DocumentParser.SUPPORTED_TYPES:
        raise HTTPException(400, f"不支持的格式: {suffix}")

    save_path = UPLOAD_DIR / Path(file.filename).name
    if save_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(file.filename).stem
        save_path = UPLOAD_DIR / f"{stem}_{timestamp}{suffix}"
    content = await file.read()
    save_path.write_bytes(content)

    doc = DocumentDAO.create(file.filename, suffix.lstrip("."), str(save_path))
    return {"id": doc.id, "filename": doc.filename}


@router.post("/documents/parse/{doc_id}", tags=["文档管理"], summary="解析文档")
async def parse_document(doc_id: int):
    """解析已上传的文档，提取文本内容"""
    doc = DocumentDAO.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    result = DocumentParser.parse(doc.file_path)
    DocumentDAO.update_text(doc_id, result["text"])
    return {"doc_id": doc_id, "metadata": result["metadata"], "text_length": len(result["text"])}


@router.post("/documents/extract/{doc_id}", tags=["实体提取"], summary="提取文档实体")
async def extract_entities(doc_id: int):
    """从已解析的文档中提取结构化实体信息"""
    doc = DocumentDAO.get_by_id(doc_id)
    if not doc or not doc.raw_text:
        raise HTTPException(400, "文档未解析，请先调用parse接口")

    extractor = EntityExtractor()
    result = await extractor.extract(doc.raw_text)

    entities = result.get("entities", [])
    EntityDAO.create_batch(doc_id, entities)
    return {"doc_id": doc_id, "entities_count": len(entities), "summary": result.get("summary", "")}


@router.post("/documents/command", tags=["文档管理"], summary="执行文档操作指令")
async def execute_command(req: CommandRequest):
    """使用自然语言指令操作文档"""
    doc = DocumentDAO.get_by_id(req.doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    commander = DocCommander()
    doc_info = f"文件名: {doc.filename}, 类型: {doc.file_type}"
    parsed = await commander.parse_command(req.command, doc_info)

    if "error" in parsed:
        raise HTTPException(400, parsed["error"])

    result = commander.execute(doc.file_path, parsed)
    return {"command": parsed, "result": result}


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
    save_path = UPLOAD_DIR / Path(file.filename).name
    if save_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(file.filename).stem
        ext = Path(file.filename).suffix
        save_path = UPLOAD_DIR / f"{stem}_{timestamp}{ext}"
    content = await file.read()
    save_path.write_bytes(content)

    filler = TemplateFiller()
    analysis = await filler.analyze_template(str(save_path))
    tpl = TemplateDAO.create(file.filename, str(save_path), json.dumps(analysis, ensure_ascii=False))
    return {"id": tpl.id, "filename": tpl.filename, "fields": analysis["field_names"]}


async def _do_fill(task_id: int, template_path: str, entities: list[dict]):
    FillTaskDAO.update_status(task_id, "processing")
    try:
        filler = TemplateFiller()
        result = await filler.fill(template_path, entities)
        FillTaskDAO.update_status(task_id, "completed",
                                  result_path=result.get("output_path"),
                                  accuracy=result.get("accuracy"))
        log.info(f"填写任务 {task_id} 完成, 准确率: {result.get('accuracy')}")
    except Exception as e:
        log.error(f"填写任务 {task_id} 失败: {e}")
        FillTaskDAO.update_status(task_id, "failed")


def _run_fill_task(task_id: int, template_path: str, entities: list[dict]):
    """BackgroundTasks 的同步包装，避免 async 任务在响应路径中被直接等待。"""
    asyncio.run(_do_fill(task_id, template_path, entities))


@router.post("/templates/fill", tags=["模板填写"], summary="自动填写模板")
async def fill_template(req: FillRequest, background_tasks: BackgroundTasks):
    """使用提取的实体数据自动填写模板，异步执行"""
    tpl = TemplateDAO.get_by_id(req.template_id)
    if not tpl:
        raise HTTPException(404, "模板不存在")

    # 收集实体
    entities = []
    if req.document_ids:
        for did in req.document_ids:
            for e in EntityDAO.get_by_document(did):
                entities.append({"type": e.entity_type, "value": e.entity_value, "confidence": e.confidence})
    else:
        for e in EntityDAO.get_all():
            entities.append({"type": e.entity_type, "value": e.entity_value, "confidence": e.confidence})

    task = FillTaskDAO.create(tpl.id)
    background_tasks.add_task(_run_fill_task, task.id, tpl.file_path, entities)
    return {"task_id": task.id, "status": "pending"}


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
