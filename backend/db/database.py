"""数据库操作封装"""
from datetime import datetime
from typing import Optional
from sqlalchemy import distinct, func, or_
from db.models import session_scope, Document, DocumentVersion, Entity, Template, FillTask, CrawledArticle


class _ExternalSession:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def _using_session(session):
    return _ExternalSession(session) if session is not None else session_scope()


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


def _apply_pagination(query, limit: int | None = None, offset: int = 0):
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query


class DocumentDAO:
    @staticmethod
    def create(filename: str, file_type: str, file_path: str, session=None) -> Document:
        with _using_session(session) as s:
            doc = Document(filename=filename, file_type=file_type, file_path=file_path)
            s.add(doc)
            s.flush()
            s.refresh(doc)
            return doc if session is not None else _expunge_one(s, doc)

    @staticmethod
    def update_text(doc_id: int, raw_text: str, session=None):
        with _using_session(session) as s:
            doc = s.get(Document, doc_id)
            if doc:
                doc.raw_text = raw_text
                doc.parsed_at = datetime.now()

    @staticmethod
    def get_all(limit: int | None = None, offset: int = 0, session=None) -> list[Document]:
        with _using_session(session) as s:
            query = s.query(Document).order_by(Document.created_at.desc())
            docs = _apply_pagination(query, limit, offset).all()
            return docs if session is not None else _expunge_list(s, docs)

    @staticmethod
    def search(keyword: str, limit: int | None = None, offset: int = 0, session=None) -> list[Document]:
        keyword = keyword.strip()
        if not keyword:
            return DocumentDAO.get_all(limit=limit, offset=offset, session=session)
        pattern = f"%{keyword}%"
        with _using_session(session) as s:
            query = (
                s.query(Document)
                .filter(or_(Document.filename.like(pattern), Document.raw_text.like(pattern)))
                .order_by(Document.created_at.desc())
            )
            docs = _apply_pagination(query, limit, offset).all()
            return docs if session is not None else _expunge_list(s, docs)

    @staticmethod
    def get_recent(limit: int = 20) -> list[Document]:
        return DocumentDAO.get_all(limit=limit, offset=0)

    @staticmethod
    def get_by_id(doc_id: int, session=None) -> Optional[Document]:
        with _using_session(session) as s:
            doc = s.get(Document, doc_id)
            return doc if session is not None else _expunge_one(s, doc)

    @staticmethod
    def delete(doc_id: int, session=None):
        with _using_session(session) as s:
            doc = s.get(Document, doc_id)
            if doc:
                s.delete(doc)

    @staticmethod
    def count() -> int:
        with session_scope() as s:
            return s.query(Document).count()

    @staticmethod
    def count_parsed() -> int:
        with session_scope() as s:
            return s.query(Document).filter(Document.raw_text.isnot(None), Document.raw_text != "").count()

    @staticmethod
    def count_by_type() -> dict[str, int]:
        with session_scope() as s:
            rows = (
                s.query(func.lower(func.coalesce(Document.file_type, "unknown")), func.count(Document.id))
                .group_by(func.lower(func.coalesce(Document.file_type, "unknown")))
                .all()
            )
            return {doc_type: count for doc_type, count in rows}


class DocumentVersionDAO:
    @staticmethod
    def create(document_id: int, file_path: str, note: str = "") -> DocumentVersion:
        with session_scope() as s:
            max_version = (
                s.query(func.max(DocumentVersion.version_no))
                .filter(DocumentVersion.document_id == document_id)
                .scalar()
                or 0
            )
            version = DocumentVersion(
                document_id=document_id,
                version_no=max_version + 1,
                file_path=file_path,
                note=note,
            )
            s.add(version)
            s.flush()
            s.refresh(version)
            return _expunge_one(s, version)

    @staticmethod
    def list_by_document(document_id: int) -> list[DocumentVersion]:
        with session_scope() as s:
            versions = (
                s.query(DocumentVersion)
                .filter(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version_no.desc())
                .all()
            )
            return _expunge_list(s, versions)

    @staticmethod
    def get_by_id(version_id: int) -> Optional[DocumentVersion]:
        with session_scope() as s:
            version = s.get(DocumentVersion, version_id)
            return _expunge_one(s, version)


class EntityDAO:
    @staticmethod
    def create_batch(doc_id: int, entities: list[dict], session=None):
        with _using_session(session) as s:
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
    def get_by_document(doc_id: int, limit: int | None = None, offset: int = 0, session=None) -> list[Entity]:
        with _using_session(session) as s:
            query = s.query(Entity).filter(Entity.document_id == doc_id)
            entities = _apply_pagination(query, limit, offset).all()
            return entities if session is not None else _expunge_list(s, entities)

    @staticmethod
    def get_all(limit: int | None = None, offset: int = 0, session=None) -> list[Entity]:
        with _using_session(session) as s:
            query = s.query(Entity)
            entities = _apply_pagination(query, limit, offset).all()
            return entities if session is not None else _expunge_list(s, entities)

    @staticmethod
    def search(
        keyword: str | None = None,
        entity_type: str | None = None,
        doc_id: int | None = None,
        limit: int | None = None,
        offset: int = 0,
        session=None,
    ) -> list[Entity]:
        with _using_session(session) as s:
            query = s.query(Entity)
            if doc_id:
                query = query.filter(Entity.document_id == doc_id)
            if entity_type:
                query = query.filter(func.lower(Entity.entity_type) == entity_type.strip().lower())
            if keyword:
                keyword = keyword.strip()
                if keyword:
                    pattern = f"%{keyword}%"
                    query = query.filter(or_(Entity.entity_value.like(pattern), Entity.context.like(pattern)))
            entities = _apply_pagination(query, limit, offset).all()
            return entities if session is not None else _expunge_list(s, entities)

    @staticmethod
    def delete_by_document(doc_id: int, session=None):
        """删除指定文档的所有实体"""
        with _using_session(session) as s:
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
    def get_cross_document_entities(min_documents: int = 2, limit: int = 100) -> list[dict]:
        """查询跨多个文档出现的实体，用于数据融合分析。"""
        with session_scope() as s:
            rows = (
                s.query(
                    Entity.entity_type,
                    Entity.entity_value,
                    func.count(Entity.id).label("count"),
                    func.count(distinct(Entity.document_id)).label("doc_count"),
                    func.avg(Entity.confidence).label("avg_confidence"),
                    func.group_concat(distinct(Document.filename)).label("documents"),
                )
                .join(Document, Entity.document_id == Document.id)
                .filter(Entity.entity_value != "")
                .group_by(Entity.entity_type, Entity.entity_value)
                .having(func.count(distinct(Entity.document_id)) >= min_documents)
                .order_by(
                    func.count(distinct(Entity.document_id)).desc(),
                    func.count(Entity.id).desc(),
                    Entity.entity_type.asc(),
                    Entity.entity_value.asc(),
                )
                .limit(limit)
                .all()
            )

        return [
            {
                "type": entity_type,
                "value": entity_value,
                "count": count,
                "doc_count": doc_count,
                "documents": sorted(documents.split(",")) if documents else [],
                "avg_confidence": avg_confidence,
            }
            for entity_type, entity_value, count, doc_count, avg_confidence, documents in rows
        ]


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
    def get_all(limit: int | None = None, offset: int = 0) -> list[Template]:
        with session_scope() as s:
            query = s.query(Template).order_by(Template.created_at.desc())
            templates = _apply_pagination(query, limit, offset).all()
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

    @staticmethod
    def get_all(limit: int | None = None, offset: int = 0) -> list[FillTask]:
        with session_scope() as s:
            query = s.query(FillTask).order_by(FillTask.created_at.desc())
            tasks = _apply_pagination(query, limit, offset).all()
            return _expunge_list(s, tasks)

    @staticmethod
    def list_by_status(status: str, limit: int | None = None, offset: int = 0) -> list[FillTask]:
        with session_scope() as s:
            query = (
                s.query(FillTask)
                .filter(FillTask.status == status)
                .order_by(FillTask.created_at.desc())
            )
            tasks = _apply_pagination(query, limit, offset).all()
            return _expunge_list(s, tasks)


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
    def get_all(limit: int | None = None, offset: int = 0) -> list[CrawledArticle]:
        with session_scope() as s:
            query = s.query(CrawledArticle).order_by(CrawledArticle.crawled_at.desc())
            articles = _apply_pagination(query, limit, offset).all()
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
