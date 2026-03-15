import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserTtsConnection(Base):
    __tablename__ = "user_tts_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider_code", name="uq_user_tts_connection"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_code: Mapped[str] = mapped_column(String(60), index=True, default="elevenlabs")
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
