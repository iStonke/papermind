from datetime import datetime

from sqlalchemy import BIGINT, CheckConstraint, DateTime, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BackupSourceState(Base):
    """Monotoner Änderungszähler für den sicherungsrelevanten Datenbestand."""

    __tablename__ = "backup_source_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_backup_source_state_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    generation: Mapped[int] = mapped_column(BIGINT, nullable=False, server_default="1")
    backed_up_generation: Mapped[int] = mapped_column(BIGINT, nullable=False, server_default="0")
    last_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
