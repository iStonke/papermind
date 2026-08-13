"""Versioned, source-grounded knowledge graph for the PaperMind LLM wiki.

Wiki pages are derived navigation artifacts.  Facts live as atomic claims and
are only trustworthy when they have source evidence pointing back to an
immutable document chunk.  Page revisions are append-only; corrections create
new revisions/claims and supersede the old knowledge instead of rewriting
history.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

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
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('source', 'entity', 'contract', 'topic', 'timeline', 'comparison', 'analysis')",
            name="ck_wiki_pages_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'needs_review', 'stale', 'archived')",
            name="ck_wiki_pages_status",
        ),
        UniqueConstraint("owner_id", "slug", name="uq_wiki_pages_owner_slug"),
        Index("ix_wiki_pages_owner_kind_status", "owner_id", "kind", "status"),
        Index(
            "uq_wiki_pages_owner_source_document",
            "owner_id",
            "source_document_id",
            unique=True,
            postgresql_where=sql_text("source_document_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review", server_default="needs_review")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "wiki_page_revisions.id",
            name="fk_wiki_pages_current_revision_id",
            use_alter=True,
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    revisions: Mapped[list["WikiPageRevision"]] = relationship(
        "WikiPageRevision",
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="WikiPageRevision.page_id",
        order_by="WikiPageRevision.revision_number.asc()",
    )
    current_revision: Mapped["WikiPageRevision | None"] = relationship(
        "WikiPageRevision",
        foreign_keys=[current_revision_id],
        post_update=True,
    )


class WikiPageRevision(Base):
    __tablename__ = "wiki_page_revisions"
    __table_args__ = (
        CheckConstraint("revision_number > 0", name="ck_wiki_page_revisions_number"),
        CheckConstraint(
            "created_by IN ('system', 'llm', 'user')",
            name="ck_wiki_page_revisions_created_by",
        ),
        UniqueConstraint("page_id", "revision_number", name="uq_wiki_page_revisions_page_number"),
        Index("ix_wiki_page_revisions_page_created", "page_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    based_on_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_page_revisions.id", ondelete="SET NULL"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1", server_default="1")
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(16), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    page: Mapped[WikiPage] = relationship(
        "WikiPage",
        back_populates="revisions",
        foreign_keys=[page_id],
    )


class WikiClaim(Base):
    __tablename__ = "wiki_claims"
    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('fact', 'inference', 'user_assertion')",
            name="ck_wiki_claims_type",
        ),
        CheckConstraint(
            "status IN ('active', 'needs_review', 'disputed', 'superseded', 'retracted', 'stale')",
            name="ck_wiki_claims_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_wiki_claims_confidence",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_wiki_claims_validity",
        ),
        UniqueConstraint("revision_id", "stable_key", name="uq_wiki_claims_revision_stable_key"),
        Index("ix_wiki_claims_page_status", "page_id", "status"),
        Index("ix_wiki_claims_owner_status", "owner_id", "status"),
        Index("ix_wiki_claims_source_document", "source_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_page_revisions.id", ondelete="CASCADE"), nullable=False
    )
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicate: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review", server_default="needs_review")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_claims.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    locked_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sql_text("false"))
    created_by: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    evidence: Mapped[list["WikiClaimEvidence"]] = relationship(
        "WikiClaimEvidence",
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="WikiClaimEvidence.created_at.asc()",
    )


class WikiClaimEvidence(Base):
    __tablename__ = "wiki_claim_evidence"
    __table_args__ = (
        CheckConstraint(
            "support_role IN ('supports', 'contradicts')",
            name="ck_wiki_claim_evidence_role",
        ),
        UniqueConstraint("claim_id", "chunk_id", "quote_hash", name="uq_wiki_claim_evidence_claim_chunk_quote"),
        Index("ix_wiki_claim_evidence_document", "document_id"),
        Index("ix_wiki_claim_evidence_chunk", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_claims.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doc_chunks.id", ondelete="CASCADE"), nullable=False
    )
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    support_role: Mapped[str] = mapped_column(String(16), nullable=False, default="supports", server_default="supports")
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped[WikiClaim] = relationship("WikiClaim", back_populates="evidence")


class WikiLink(Base):
    __tablename__ = "wiki_links"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'needs_review', 'retracted')",
            name="ck_wiki_links_status",
        ),
        CheckConstraint("from_page_id <> to_page_id", name="ck_wiki_links_not_self"),
        UniqueConstraint("from_page_id", "to_page_id", "relation", name="uq_wiki_links_relation"),
        Index("ix_wiki_links_owner_from", "owner_id", "from_page_id"),
        Index("ix_wiki_links_owner_to", "owner_id", "to_page_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    to_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_claims.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review", server_default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WikiUpdateProposal(Base):
    __tablename__ = "wiki_update_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'validated', 'applied', 'rejected', 'failed')",
            name="ck_wiki_update_proposals_status",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_wiki_update_proposals_owner_key"),
        Index("ix_wiki_update_proposals_owner_status", "owner_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    source_chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True
    )
    base_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_page_revisions.id", ondelete="SET NULL"), nullable=True
    )
    applied_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_page_revisions.id", ondelete="SET NULL"), nullable=True
    )
    proposal_type: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1", server_default="1")
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WikiBackfillRun(Base):
    __tablename__ = "wiki_backfill_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'done', 'failed', 'cancelled')",
            name="ck_wiki_backfill_runs_status",
        ),
        CheckConstraint("batch_size >= 1 AND batch_size <= 50", name="ck_wiki_backfill_runs_batch_size"),
        CheckConstraint(
            "document_limit IS NULL OR (document_limit >= 1 AND document_limit <= 5000)",
            name="ck_wiki_backfill_runs_document_limit",
        ),
        CheckConstraint(
            "total_documents >= 0 AND processed_documents >= 0 AND updated_documents >= 0 "
            "AND review_proposals >= 0 AND failed_documents >= 0",
            name="ck_wiki_backfill_runs_counts",
        ),
        Index("ix_wiki_backfill_runs_owner_created", "owner_id", "created_at"),
        Index(
            "uq_wiki_backfill_runs_owner_active",
            "owner_id",
            unique=True,
            postgresql_where=sql_text("status IN ('queued', 'running', 'paused')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    document_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cursor_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    review_proposals: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WikiEvent(Base):
    __tablename__ = "wiki_events"
    __table_args__ = (Index("ix_wiki_events_owner_created", "owner_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True
    )
    revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_page_revisions.id", ondelete="SET NULL"), nullable=True
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_claims.id", ondelete="SET NULL"), nullable=True
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_update_proposals.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=sql_text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
