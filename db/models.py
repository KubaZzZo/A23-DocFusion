"""数据模型定义"""
from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import DB_PATH

Base = declarative_base()
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH}"


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_path = Column(Text, nullable=False)
    raw_text = Column(Text)
    parsed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_value = Column(Text, nullable=False)
    context = Column(Text)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    document = relationship("Document", back_populates="entities")


class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    fields_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    fill_tasks = relationship("FillTask", back_populates="template", cascade="all, delete-orphan")


class FillTask(Base):
    __tablename__ = "fill_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    status = Column(String(20), default="pending")
    result_path = Column(Text)
    accuracy = Column(Float)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    template = relationship("Template", back_populates="fill_tasks")


class CrawledArticle(Base):
    __tablename__ = "crawled_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500))
    author = Column(String(100))
    source = Column(String(200))
    url = Column(Text)
    publish_date = Column(String(50))
    content = Column(Text)
    category = Column(String(50))
    crawled_at = Column(DateTime, default=datetime.now)


# 数据库初始化
engine = create_engine(DEFAULT_DATABASE_URL, echo=False)
_default_engine = engine
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
_database_url = DEFAULT_DATABASE_URL


def configure_database(database_url: str):
    """Rebind the global engine/session factory to a database URL."""
    global engine, SessionLocal, _database_url
    old_engine = engine
    _database_url = database_url
    if database_url == DEFAULT_DATABASE_URL:
        engine = _default_engine
    else:
        engine = create_engine(database_url, echo=False)
    SessionLocal.configure(bind=engine)
    if old_engine is not _default_engine and old_engine is not engine:
        old_engine.dispose()


def reset_database():
    """Restore the default SQLite database binding."""
    configure_database(DEFAULT_DATABASE_URL)


def get_database_url() -> str:
    return _database_url


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    """获取数据库session（上下文管理器，自动关闭）"""
    return SessionLocal()


@contextmanager
def session_scope():
    """提供一个事务性的session上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
