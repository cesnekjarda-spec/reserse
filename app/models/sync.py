import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    triggered_by: Mapped[str] = mapped_column(String(80), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_sources: Mapped[int] = mapped_column(Integer, default=0)
    total_articles_created: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)

    items = relationship("SyncRunItem", back_populates="sync_run", cascade="all, delete-orphan")


class SyncRunItem(Base):
    __tablename__ = "sync_run_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sync_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("sync_runs.id", ondelete="CASCADE"), index=True)
    source_name: Mapped[str] = mapped_column(String(160))
    source_rss_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    articles_created: Mapped[int] = mapped_column(Integer, default=0)

    sync_run = relationship("SyncRun", back_populates="items")
