import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Brief(Base):
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("topic_id", name="uq_brief_topic"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(220))
    summary: Mapped[str] = mapped_column(Text)
    what_happened: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    watchlist: Mapped[str] = mapped_column(Text)
    key_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    topic = relationship("Topic")

    @property
    def key_points(self) -> list[str]:
        if not self.key_points_json:
            return []
        try:
            return json.loads(self.key_points_json)
        except Exception:
            return []

    def set_key_points(self, items: list[str]) -> None:
        self.key_points_json = json.dumps(items, ensure_ascii=False)

    @property
    def article_ids(self) -> list[str]:
        if not self.article_ids_json:
            return []
        try:
            return json.loads(self.article_ids_json)
        except Exception:
            return []

    def set_article_ids(self, items: list[str]) -> None:
        self.article_ids_json = json.dumps(items, ensure_ascii=False)
