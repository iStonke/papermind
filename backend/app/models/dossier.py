import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Dossier(Base):
    __tablename__ = "dossiers"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'closed')", name="ck_dossiers_state"),
        Index("ix_dossiers_owner_updated", "owner_id", "updated_at"),
        Index("ix_dossiers_owner_archived", "owner_id", "archived_at"),
        Index(
            "ix_dossiers_owner_favorite",
            "owner_id",
            "is_favorite",
            postgresql_where=text("is_favorite"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    dossier_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    properties: Mapped[list["DossierProperty"]] = relationship(
        "DossierProperty",
        back_populates="dossier",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DossierProperty.sort_order.asc()",
    )
    groups: Mapped[list["DossierGroup"]] = relationship(
        "DossierGroup",
        back_populates="dossier",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DossierGroup.sort_order.asc()",
    )
    items: Mapped[list["DossierItem"]] = relationship(
        "DossierItem",
        back_populates="dossier",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DossierItem.sort_order.asc()",
    )


class DossierProperty(Base):
    __tablename__ = "dossier_properties"
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('text', 'date', 'number', 'boolean')",
            name="ck_dossier_properties_value_type",
        ),
        Index("ix_dossier_properties_dossier_sort", "dossier_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    dossier: Mapped[Dossier] = relationship("Dossier", back_populates="properties", lazy="select")


class DossierGroup(Base):
    __tablename__ = "dossier_groups"
    __table_args__ = (Index("ix_dossier_groups_dossier_sort", "dossier_id", "sort_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    pos_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    pos_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    dossier: Mapped[Dossier] = relationship("Dossier", back_populates="groups", lazy="select")


class DossierItem(Base):
    __tablename__ = "dossier_items"
    __table_args__ = (
        CheckConstraint("item_type IN ('document', 'note', 'link')", name="ck_dossier_items_type"),
        CheckConstraint(
            "(item_type = 'document' AND document_id IS NOT NULL) OR "
            "(item_type = 'note' AND document_id IS NULL) OR "
            "(item_type = 'link' AND document_id IS NULL AND link_url IS NOT NULL)",
            name="ck_dossier_items_payload",
        ),
        Index("ix_dossier_items_dossier_group_sort", "dossier_id", "group_id", "sort_order"),
        Index("ix_dossier_items_document_id", "document_id"),
        Index("ix_dossier_items_attached_to_item_id", "attached_to_item_id"),
        Index(
            "uq_dossier_items_document_once",
            "dossier_id",
            "document_id",
            unique=True,
            postgresql_where=text("item_type = 'document' AND document_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossier_groups.id", ondelete="SET NULL"), nullable=True
    )
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    pos_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    pos_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    attached_to_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossier_items.id", ondelete="SET NULL"), nullable=True
    )
    note_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    link_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    dossier: Mapped[Dossier] = relationship("Dossier", back_populates="items", lazy="select")
    document: Mapped["Document | None"] = relationship("Document", lazy="select")
