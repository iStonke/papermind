import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SearchEvent(Base):
    """Protokolliert einen abgeschickten Suchbegriff (owner-scoped).

    Nur committete Suchen (Enter), normalisiert und gekürzt. Dient der
    Dashboard-Auswertung „Top-Suchbegriffe" – rein persönlich, RLS-isoliert.
    """

    __tablename__ = "search_events"
    __table_args__ = (
        Index("ix_search_events_owner_created", "owner_id", "created_at"),
        Index("ix_search_events_owner_term", "owner_id", "term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
