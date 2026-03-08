from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


Base = declarative_base()


engine_kwargs = {"future": True, "pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models explicitly so their tables are registered on Base.metadata.
    from app.models.user import User
    from app.models.topic import Topic
    from app.models.source import Source
    from app.models.article import Article
    from app.models.subscription import UserTopicSubscription, UserArticleRead
    from app.models.session import UserSession
    from app.models.sync import SyncRun, SyncRunItem

    # Be defensive on PostgreSQL: ensure the default schema exists before DDL.
    if settings.database_url.startswith("postgresql"):
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))

    # Create tables in explicit dependency order. This avoids edge cases where
    # backend/DDL ordering can fail during first bootstrap on a clean database.
    ordered_tables = [
        User.__table__,
        Topic.__table__,
        Source.__table__,
        Article.__table__,
        UserTopicSubscription.__table__,
        UserArticleRead.__table__,
        UserSession.__table__,
        SyncRun.__table__,
        SyncRunItem.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=ordered_tables)
