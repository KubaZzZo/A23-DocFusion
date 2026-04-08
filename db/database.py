"""数据库操作封装"""
from datetime import datetime
from typing import Optional
from sqlalchemy import func
from db.models import session_scope, Document, Entity, Template, FillTask, CrawledArticle


def _expunge_list(session, items):
    """将对象列表从session中分离，使其在session关闭后仍可访问"""
    for item in items:
        session.expunge(item)
    return items


def _expunge_one(session, item):
    """将单个对象从session中分离"""
    if item:
        session.expunge(item)
    return item


class DocumentDAO:
    @staticmethod
    def create(filename: str, file_type: str, file_path: str) -> Document:
        with session_scope() as s:
            doc = Document(filename=filename, file_type=file_type, file_path=file_path)
            s.add(doc)
            s.flush()
            s.refresh(doc)
            return _expunge_one(s, doc)

    @staticmethod
    def update_text(doc_id: int, raw_text: str):
        with session_scope() as s:
            doc = s.get(Document, doc_id)
            if doc:
                doc.raw_text = raw_text
                doc.parsed_at = datetime.now()

    @staticmethod
    def get_all() -> list[Document]:
        with session_scope() as s:
            docs = s.query(Document).order_by(Document.created_at.desc()).all()
            return _expunge_list(s, docs)

    @staticmethod
    def get_by_id(doc_id: int) -> Optional[Document]:
        with session_scope() as s:
            doc = s.get(Document, doc_id)
            return _expunge_one(s, doc)

    @staticmethod
    def delete(doc_id: int):
        with session_scope() as s:
            doc = s.get(Document, doc_id)
            if doc:
                s.delete(doc)

    @staticmethod
    def count() -> int:
        with session_scope() as s:
            return s.query(Document).count()


class EntityDAO:
    @staticmethod
    def create_batch(doc_id: int, entities: list[dict]):
        with session_scope() as s:
            for e in entities:
                entity = Entity(
                    document_id=doc_id,
                    entity_type=e.get("type", "unknown"),
                    entity_value=e.get("value", ""),
                    context=e.get("context", ""),
                    confidence=e.get("confidence", 0.0),
                )
                s.add(entity)

    @staticmethod
    def get_by_document(doc_id: int) -> list[Entity]:
        with session_scope() as s:
            entities = s.query(Entity).filter(Entity.document_id == doc_id).all()
            return _expunge_list(s, entities)

    @staticmethod
    def get_all() -> list[Entity]:
        with session_scope() as s:
            entities = s.query(Entity).all()
            return _expunge_list(s, entities)

    @staticmethod
    def search(keyword: str) -> list[Entity]:
        with session_scope() as s:
            entities = s.query(Entity).filter(
                Entity.entity_value.contains(keyword)
            ).all()
            return _expunge_list(s, entities)

    @staticmethod
    def delete_by_document(doc_id: int):
        """删除指定文档的所有实体"""
        with session_scope() as s:
            s.query(Entity).filter(Entity.document_id == doc_id).delete()

    @staticmethod
    def count() -> int:
        with session_scope() as s:
            return s.query(Entity).count()

    @staticmethod
    def count_by_type() -> dict[str, int]:
        with session_scope() as s:
            rows = (
                s.query(Entity.entity_type, func.count(Entity.id))
                .group_by(Entity.entity_type)
                .all()
            )
            return {entity_type: count for entity_type, count in rows}

    @staticmethod
    def get_cross_document_entities(min_documents: int = 2) -> list[dict]:
        """查询跨多个文档出现的实体，用于数据融合分析。"""
        with session_scope() as s:
            rows = (
                s.query(
                    Entity.entity_type,
                    Entity.entity_value,
                    Document.filename,
                    Entity.confidence,
                )
                .join(Document, Entity.document_id == Document.id)
                .filter(Entity.entity_value != "")
                .all()
            )

        grouped = {}
        for entity_type, entity_value, filename, confidence in rows:
            key = (entity_type, entity_value)
            item = grouped.setdefault(
                key,
                {
                    "type": entity_type,
                    "value": entity_value,
                    "count": 0,
                    "documents": set(),
                    "confidences": [],
                },
            )
            item["count"] += 1
            item["documents"].add(filename)
            if confidence is not None:
                item["confidences"].append(confidence)

        fused = []
        for item in grouped.values():
            doc_count = len(item["documents"])
            if doc_count < min_documents:
                continue
            confidences = item.pop("confidences")
            item["doc_count"] = doc_count
            item["documents"] = sorted(item["documents"])
            item["avg_confidence"] = (
                sum(confidences) / len(confidences)
                if confidences else None
            )
            fused.append(item)

        return sorted(fused, key=lambda x: (-x["doc_count"], -x["count"], x["type"], x["value"]))


class TemplateDAO:
    @staticmethod
    def create(filename: str, file_path: str, fields_json: str = "") -> Template:
        with session_scope() as s:
            tpl = Template(filename=filename, file_path=file_path, fields_json=fields_json)
            s.add(tpl)
            s.flush()
            s.refresh(tpl)
            return _expunge_one(s, tpl)

    @staticmethod
    def get_all() -> list[Template]:
        with session_scope() as s:
            templates = s.query(Template).order_by(Template.created_at.desc()).all()
            return _expunge_list(s, templates)

    @staticmethod
    def get_by_id(tpl_id: int) -> Optional[Template]:
        with session_scope() as s:
            tpl = s.get(Template, tpl_id)
            return _expunge_one(s, tpl)

    @staticmethod
    def count() -> int:
        with session_scope() as s:
            return s.query(Template).count()


class FillTaskDAO:
    @staticmethod
    def create(template_id: int) -> FillTask:
        with session_scope() as s:
            task = FillTask(template_id=template_id)
            s.add(task)
            s.flush()
            s.refresh(task)
            return _expunge_one(s, task)

    @staticmethod
    def update_status(task_id: int, status: str, result_path: str = None, accuracy: float = None):
        with session_scope() as s:
            task = s.get(FillTask, task_id)
            if task:
                task.status = status
                if status == "processing":
                    task.started_at = datetime.now()
                if status in ("completed", "failed"):
                    task.completed_at = datetime.now()
                if result_path:
                    task.result_path = result_path
                if accuracy is not None:
                    task.accuracy = accuracy

    @staticmethod
    def get_by_id(task_id: int) -> Optional[FillTask]:
        with session_scope() as s:
            task = s.get(FillTask, task_id)
            return _expunge_one(s, task)


class CrawledArticleDAO:
    @staticmethod
    def create(title: str, author: str, source: str, url: str,
               publish_date: str, content: str, category: str = "") -> CrawledArticle:
        with session_scope() as s:
            article = CrawledArticle(
                title=title, author=author, source=source, url=url,
                publish_date=publish_date, content=content, category=category,
                crawled_at=datetime.now()
            )
            s.add(article)
            s.flush()
            s.refresh(article)
            return _expunge_one(s, article)

    @staticmethod
    def create_batch(articles: list[dict]) -> list[CrawledArticle]:
        with session_scope() as s:
            result = []
            for a in articles:
                article = CrawledArticle(
                    title=a.get("title", ""),
                    author=a.get("author", ""),
                    source=a.get("source", ""),
                    url=a.get("url", ""),
                    publish_date=a.get("publish_date", ""),
                    content=a.get("content", ""),
                    category=a.get("category", ""),
                    crawled_at=datetime.now()
                )
                s.add(article)
                result.append(article)
            s.flush()
            for a in result:
                s.refresh(a)
            return _expunge_list(s, result)

    @staticmethod
    def get_all() -> list[CrawledArticle]:
        with session_scope() as s:
            articles = s.query(CrawledArticle).order_by(CrawledArticle.crawled_at.desc()).all()
            return _expunge_list(s, articles)

    @staticmethod
    def get_by_id(article_id: int) -> Optional[CrawledArticle]:
        with session_scope() as s:
            article = s.get(CrawledArticle, article_id)
            return _expunge_one(s, article)

    @staticmethod
    def count() -> int:
        with session_scope() as s:
            return s.query(CrawledArticle).count()
