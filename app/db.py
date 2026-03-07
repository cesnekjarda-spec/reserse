from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


Base = declarative_base()

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.article import Article
    from app.models.session import UserSession
    from app.models.source import Source
    from app.models.subscription import UserArticleRead, UserTopicSubscription
    from app.models.sync import SyncRun, SyncRunItem
    from app.models.topic import Topic
    from app.models.user import User

    Base.metadata.create_all(bind=engine)
