"""source-grounded, versioned LLM wiki and persistent chat sessions.

Revision ID: 071_llm_wiki_trust_foundation
Revises: 070_dossier_item_connections
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID


revision: str = "071_llm_wiki_trust_foundation"
down_revision: Union[str, None] = "070_dossier_item_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"
_BACKUP_TABLES = (
    "chat_sessions",
    "chat_messages",
    "wiki_pages",
    "wiki_page_revisions",
    "wiki_claims",
    "wiki_claim_evidence",
    "wiki_links",
    "wiki_update_proposals",
    "wiki_events",
)


def _grant(table: str) -> None:
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role}";
              END IF;
            END $$;
            """
        )


def _enable_owner_rls(table: str, extra_check: str = "") -> None:
    condition = f"owner_id = {_OWNER_EXPR}{extra_check}"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_owner_isolation ON {table} "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK ({condition})"
    )
    _grant(table)


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("client_session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "client_session_id", name="uq_chat_sessions_owner_client"),
    )
    op.create_index("ix_chat_sessions_owner_id", "chat_sessions", ["owner_id"])
    op.create_index("ix_chat_sessions_owner_updated", "chat_sessions", ["owner_id", "updated_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("knowledge_trace", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_chat_messages_role"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_chat_messages_session_sequence"),
    )
    op.create_index("ix_chat_messages_owner_id", "chat_messages", ["owner_id"])
    op.create_index("ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"])

    op.create_table(
        "wiki_pages",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="needs_review"),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("current_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('source', 'entity', 'contract', 'topic', 'timeline', 'comparison', 'analysis')",
            name="ck_wiki_pages_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_review', 'stale', 'archived')",
            name="ck_wiki_pages_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_wiki_pages_owner_slug"),
    )
    op.create_index("ix_wiki_pages_owner_id", "wiki_pages", ["owner_id"])
    op.create_index("ix_wiki_pages_owner_kind_status", "wiki_pages", ["owner_id", "kind", "status"])
    op.create_index(
        "uq_wiki_pages_owner_source_document",
        "wiki_pages",
        ["owner_id", "source_document_id"],
        unique=True,
        postgresql_where=sa.text("source_document_id IS NOT NULL"),
    )
    op.create_index("ix_wiki_pages_search_vector", "wiki_pages", ["search_vector"], postgresql_using="gin")

    op.create_table(
        "wiki_page_revisions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("based_on_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=16), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision_number > 0", name="ck_wiki_page_revisions_number"),
        sa.CheckConstraint(
            "created_by IN ('system', 'llm', 'user')",
            name="ck_wiki_page_revisions_created_by",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["based_on_revision_id"], ["wiki_page_revisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "revision_number", name="uq_wiki_page_revisions_page_number"),
    )
    op.create_index("ix_wiki_page_revisions_owner_id", "wiki_page_revisions", ["owner_id"])
    op.create_index("ix_wiki_page_revisions_page_created", "wiki_page_revisions", ["page_id", "created_at"])
    op.create_foreign_key(
        "fk_wiki_pages_current_revision_id",
        "wiki_pages",
        "wiki_page_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "wiki_claims",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("stable_key", sa.String(length=160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("predicate", sa.String(length=80), nullable=True),
        sa.Column("object_text", sa.Text(), nullable=True),
        sa.Column("claim_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="needs_review"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("supersedes_claim_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("locked_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "claim_type IN ('fact', 'inference', 'user_assertion')",
            name="ck_wiki_claims_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_review', 'disputed', 'superseded', 'retracted', 'stale')",
            name="ck_wiki_claims_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_wiki_claims_confidence",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_wiki_claims_validity",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["wiki_page_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_claim_id"], ["wiki_claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "stable_key", name="uq_wiki_claims_revision_stable_key"),
    )
    op.create_index("ix_wiki_claims_owner_id", "wiki_claims", ["owner_id"])
    op.create_index("ix_wiki_claims_page_status", "wiki_claims", ["page_id", "status"])
    op.create_index("ix_wiki_claims_owner_status", "wiki_claims", ["owner_id", "status"])
    op.create_index("ix_wiki_claims_source_document", "wiki_claims", ["source_document_id"])

    op.create_table(
        "wiki_claim_evidence",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("quote_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_content_hash", sa.String(length=64), nullable=False),
        sa.Column("document_text_hash", sa.String(length=64), nullable=True),
        sa.Column("support_role", sa.String(length=16), nullable=False, server_default="supports"),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "support_role IN ('supports', 'contradicts')",
            name="ck_wiki_claim_evidence_role",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["wiki_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["doc_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "chunk_id", "quote_hash", name="uq_wiki_claim_evidence_claim_chunk_quote"),
    )
    op.create_index("ix_wiki_claim_evidence_owner_id", "wiki_claim_evidence", ["owner_id"])
    op.create_index("ix_wiki_claim_evidence_document", "wiki_claim_evidence", ["document_id"])
    op.create_index("ix_wiki_claim_evidence_chunk", "wiki_claim_evidence", ["chunk_id"])

    op.create_table(
        "wiki_links",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("from_page_id", UUID(as_uuid=True), nullable=False),
        sa.Column("to_page_id", UUID(as_uuid=True), nullable=False),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("claim_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="needs_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('active', 'needs_review', 'retracted')",
            name="ck_wiki_links_status",
        ),
        sa.CheckConstraint("from_page_id <> to_page_id", name="ck_wiki_links_not_self"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["wiki_claims.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_page_id", "to_page_id", "relation", name="uq_wiki_links_relation"),
    )
    op.create_index("ix_wiki_links_owner_id", "wiki_links", ["owner_id"])
    op.create_index("ix_wiki_links_owner_from", "wiki_links", ["owner_id", "from_page_id"])
    op.create_index("ix_wiki_links_owner_to", "wiki_links", ["owner_id", "to_page_id"])

    op.create_table(
        "wiki_update_proposals",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_chat_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("page_id", UUID(as_uuid=True), nullable=True),
        sa.Column("base_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("applied_revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("validation_errors", JSONB(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'validated', 'applied', 'rejected', 'failed')",
            name="ck_wiki_update_proposals_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_chat_session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["base_revision_id"], ["wiki_page_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_revision_id"], ["wiki_page_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_wiki_update_proposals_owner_key"),
    )
    op.create_index("ix_wiki_update_proposals_owner_id", "wiki_update_proposals", ["owner_id"])
    op.create_index(
        "ix_wiki_update_proposals_owner_status",
        "wiki_update_proposals",
        ["owner_id", "status", "created_at"],
    )

    op.create_table(
        "wiki_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("page_id", UUID(as_uuid=True), nullable=True),
        sa.Column("revision_id", UUID(as_uuid=True), nullable=True),
        sa.Column("claim_id", UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revision_id"], ["wiki_page_revisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["claim_id"], ["wiki_claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposal_id"], ["wiki_update_proposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wiki_events_owner_id", "wiki_events", ["owner_id"])
    op.create_index("ix_wiki_events_owner_created", "wiki_events", ["owner_id", "created_at"])

    # Vector columns are created through SQL because PaperMind deliberately has
    # no Python pgvector ORM dependency.  This mirrors doc_embeddings.
    op.execute(
        """
        CREATE TABLE wiki_page_embeddings (
            page_id uuid PRIMARY KEY REFERENCES wiki_pages(id) ON DELETE CASCADE,
            owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            revision_id uuid NOT NULL REFERENCES wiki_page_revisions(id) ON DELETE CASCADE,
            model varchar(128) NOT NULL,
            dim integer NOT NULL,
            embedding vector(1024) NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_wiki_page_embeddings_dim CHECK (dim = 1024)
        )
        """
    )
    op.create_index("ix_wiki_page_embeddings_owner_id", "wiki_page_embeddings", ["owner_id"])
    op.execute(
        "CREATE INDEX ix_wiki_page_embeddings_hnsw ON wiki_page_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Full-text navigation over the current title + revision content.
    op.execute(
        """
        CREATE FUNCTION update_wiki_page_search_vector()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.search_vector =
                setweight(to_tsvector('german', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('german', coalesce(NEW.search_text, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.title, '') || ' ' || coalesce(NEW.search_text, '')), 'C');
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER wiki_pages_search_vector_update BEFORE INSERT OR UPDATE OF title, search_text "
        "ON wiki_pages FOR EACH ROW EXECUTE FUNCTION update_wiki_page_search_vector()"
    )

    # Revisions and event log are append-only. GDPR/user deletion remains
    # possible through cascading DELETEs, but historical rows cannot be edited.
    op.execute(
        """
        CREATE FUNCTION prevent_wiki_append_only_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'wiki history is append-only';
        END;
        $$
        """
    )
    for table in ("wiki_page_revisions", "wiki_events"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_wiki_append_only_update()"
        )

    # Fact activation is a database invariant, not a prompt convention.  The
    # deferred trigger permits inserting claim + evidence in one transaction.
    op.execute(
        """
        CREATE FUNCTION enforce_active_wiki_fact_evidence()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.claim_type = 'fact' AND NEW.status = 'active' AND NOT EXISTS (
                SELECT 1 FROM wiki_claim_evidence e
                WHERE e.claim_id = NEW.id AND e.owner_id = NEW.owner_id AND e.support_role = 'supports'
            ) THEN
                RAISE EXCEPTION 'active wiki fact requires supporting source evidence'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER wiki_claims_require_evidence "
        "AFTER INSERT OR UPDATE OF status, claim_type ON wiki_claims "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION enforce_active_wiki_fact_evidence()"
    )

    # Losing the final supporting source can never leave an apparently active
    # fact behind (reindex, document deletion, manual evidence correction).
    op.execute(
        """
        CREATE FUNCTION stale_wiki_claim_on_evidence_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.support_role = 'supports' AND NOT EXISTS (
                SELECT 1 FROM wiki_claim_evidence e
                WHERE e.claim_id = OLD.claim_id AND e.id <> OLD.id AND e.support_role = 'supports'
            ) THEN
                UPDATE wiki_claims
                SET status = CASE WHEN status = 'active' THEN 'stale' ELSE status END,
                    updated_at = now()
                WHERE id = OLD.claim_id;
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER wiki_claim_evidence_stale_claim BEFORE DELETE ON wiki_claim_evidence "
        "FOR EACH ROW EXECUTE FUNCTION stale_wiki_claim_on_evidence_delete()"
    )

    _enable_owner_rls("chat_sessions")
    _enable_owner_rls(
        "chat_messages",
        " AND EXISTS (SELECT 1 FROM chat_sessions cs WHERE cs.id = chat_messages.session_id "
        f"AND cs.owner_id = {_OWNER_EXPR})",
    )
    _enable_owner_rls(
        "wiki_pages",
        " AND (source_document_id IS NULL OR EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = wiki_pages.source_document_id AND d.owner_id = {_OWNER_EXPR}))",
    )
    _enable_owner_rls(
        "wiki_page_revisions",
        " AND EXISTS (SELECT 1 FROM wiki_pages p WHERE p.id = wiki_page_revisions.page_id "
        f"AND p.owner_id = {_OWNER_EXPR})",
    )
    _enable_owner_rls(
        "wiki_claims",
        " AND EXISTS (SELECT 1 FROM wiki_pages p WHERE p.id = wiki_claims.page_id "
        f"AND p.owner_id = {_OWNER_EXPR}) "
        "AND EXISTS (SELECT 1 FROM wiki_page_revisions r WHERE r.id = wiki_claims.revision_id "
        f"AND r.owner_id = {_OWNER_EXPR})",
    )
    _enable_owner_rls(
        "wiki_claim_evidence",
        " AND EXISTS (SELECT 1 FROM wiki_claims c WHERE c.id = wiki_claim_evidence.claim_id "
        f"AND c.owner_id = {_OWNER_EXPR}) "
        "AND EXISTS (SELECT 1 FROM documents d WHERE d.id = wiki_claim_evidence.document_id "
        f"AND d.owner_id = {_OWNER_EXPR})",
    )
    _enable_owner_rls(
        "wiki_links",
        " AND EXISTS (SELECT 1 FROM wiki_pages p WHERE p.id = wiki_links.from_page_id "
        f"AND p.owner_id = {_OWNER_EXPR}) "
        "AND EXISTS (SELECT 1 FROM wiki_pages p WHERE p.id = wiki_links.to_page_id "
        f"AND p.owner_id = {_OWNER_EXPR})",
    )
    _enable_owner_rls("wiki_update_proposals")
    _enable_owner_rls("wiki_events")
    _enable_owner_rls(
        "wiki_page_embeddings",
        " AND EXISTS (SELECT 1 FROM wiki_pages p WHERE p.id = wiki_page_embeddings.page_id "
        f"AND p.owner_id = {_OWNER_EXPR})",
    )

    for table in _BACKUP_TABLES:
        op.execute(
            f"CREATE TRIGGER backup_source_dirty_{table} "
            f"AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
        )

    # Existing one-document notes remain visible but are explicitly unverified.
    # No claim is created from legacy prose, so it cannot become a trusted fact.
    op.execute(
        """
        INSERT INTO wiki_pages (
            id, owner_id, slug, title, kind, status, source_document_id, search_text
        )
        SELECT
            gen_random_uuid(), d.owner_id, 'quelle-' || d.id::text,
            COALESCE(NULLIF(d.display_name, ''), NULLIF(d.original_filename, ''), 'Dokument'),
            'source', 'needs_review', d.id, w.content
        FROM document_wiki_entries w
        JOIN documents d ON d.id = w.document_id
        """
    )
    op.execute(
        """
        INSERT INTO wiki_page_revisions (
            id, owner_id, page_id, revision_number, markdown, content_hash,
            schema_version, created_by, change_reason
        )
        SELECT
            gen_random_uuid(), p.owner_id, p.id, 1, w.content, md5(w.content),
            'legacy-1', 'system', 'Legacy-Dokumentnotiz ungeprüft übernommen'
        FROM wiki_pages p
        JOIN document_wiki_entries w ON w.document_id = p.source_document_id
        WHERE p.kind = 'source'
        """
    )
    op.execute(
        """
        UPDATE wiki_pages p
        SET current_revision_id = r.id, updated_at = now()
        FROM wiki_page_revisions r
        WHERE r.page_id = p.id AND r.revision_number = 1
        """
    )


def downgrade() -> None:
    for table in reversed(_BACKUP_TABLES):
        op.execute(f"DROP TRIGGER backup_source_dirty_{table} ON {table}")

    op.execute("DROP TRIGGER wiki_claim_evidence_stale_claim ON wiki_claim_evidence")
    op.execute("DROP FUNCTION stale_wiki_claim_on_evidence_delete()")
    op.execute("DROP TRIGGER wiki_claims_require_evidence ON wiki_claims")
    op.execute("DROP FUNCTION enforce_active_wiki_fact_evidence()")
    for table in ("wiki_events", "wiki_page_revisions"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION prevent_wiki_append_only_update()")
    op.execute("DROP TRIGGER wiki_pages_search_vector_update ON wiki_pages")
    op.execute("DROP FUNCTION update_wiki_page_search_vector()")

    for table in (
        "wiki_page_embeddings",
        "wiki_events",
        "wiki_update_proposals",
        "wiki_links",
        "wiki_claim_evidence",
        "wiki_claims",
        "wiki_page_revisions",
        "wiki_pages",
        "chat_messages",
        "chat_sessions",
    ):
        op.execute(f"DROP POLICY {table}_owner_isolation ON {table}")

    op.drop_index("ix_wiki_page_embeddings_hnsw", table_name="wiki_page_embeddings")
    op.drop_index("ix_wiki_page_embeddings_owner_id", table_name="wiki_page_embeddings")
    op.drop_table("wiki_page_embeddings")
    op.drop_index("ix_wiki_events_owner_created", table_name="wiki_events")
    op.drop_index("ix_wiki_events_owner_id", table_name="wiki_events")
    op.drop_table("wiki_events")
    op.drop_index("ix_wiki_update_proposals_owner_status", table_name="wiki_update_proposals")
    op.drop_index("ix_wiki_update_proposals_owner_id", table_name="wiki_update_proposals")
    op.drop_table("wiki_update_proposals")
    op.drop_index("ix_wiki_links_owner_to", table_name="wiki_links")
    op.drop_index("ix_wiki_links_owner_from", table_name="wiki_links")
    op.drop_index("ix_wiki_links_owner_id", table_name="wiki_links")
    op.drop_table("wiki_links")
    op.drop_index("ix_wiki_claim_evidence_chunk", table_name="wiki_claim_evidence")
    op.drop_index("ix_wiki_claim_evidence_document", table_name="wiki_claim_evidence")
    op.drop_index("ix_wiki_claim_evidence_owner_id", table_name="wiki_claim_evidence")
    op.drop_table("wiki_claim_evidence")
    op.drop_index("ix_wiki_claims_source_document", table_name="wiki_claims")
    op.drop_index("ix_wiki_claims_owner_status", table_name="wiki_claims")
    op.drop_index("ix_wiki_claims_page_status", table_name="wiki_claims")
    op.drop_index("ix_wiki_claims_owner_id", table_name="wiki_claims")
    op.drop_table("wiki_claims")
    op.drop_constraint("fk_wiki_pages_current_revision_id", "wiki_pages", type_="foreignkey")
    op.drop_index("ix_wiki_page_revisions_page_created", table_name="wiki_page_revisions")
    op.drop_index("ix_wiki_page_revisions_owner_id", table_name="wiki_page_revisions")
    op.drop_table("wiki_page_revisions")
    op.drop_index("ix_wiki_pages_search_vector", table_name="wiki_pages")
    op.drop_index("uq_wiki_pages_owner_source_document", table_name="wiki_pages")
    op.drop_index("ix_wiki_pages_owner_kind_status", table_name="wiki_pages")
    op.drop_index("ix_wiki_pages_owner_id", table_name="wiki_pages")
    op.drop_table("wiki_pages")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_owner_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_owner_updated", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_owner_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
