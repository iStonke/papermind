"""add pgvector embeddings and chunk tables

Revision ID: 010_ap8_embeddings
Revises: 009_documents_unread_flag
Create Date: 2026-02-27 16:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010_ap8_embeddings"
down_revision: Union[str, None] = "009_documents_unread_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIMENSION = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.add_column("documents", sa.Column("text_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("embedding_status", sa.String(length=16), nullable=False, server_default=sa.text("'not_started'")),
    )
    op.add_column("documents", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("embedding_dim", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_embedding_status", "documents", ["embedding_status"], unique=False)
    op.create_index("ix_documents_text_hash", "documents", ["text_hash"], unique=False)
    op.create_check_constraint(
        "ck_documents_embedding_status",
        "documents",
        "embedding_status IN ('not_started', 'queued', 'running', 'done', 'failed')",
    )

    op.create_table(
        "doc_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_len", sa.Integer(), nullable=False),
        sa.Column("token_len", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_doc_chunks"),
        sa.UniqueConstraint("doc_id", "chunk_index", name="uq_doc_chunks_doc_chunk_index"),
    )
    op.create_index("ix_doc_chunks_doc_id", "doc_chunks", ["doc_id"], unique=False)
    op.create_index("ix_doc_chunks_chunk_index", "doc_chunks", ["chunk_index"], unique=False)
    op.create_index("ix_doc_chunks_content_hash", "doc_chunks", ["content_hash"], unique=False)

    op.create_table(
        "doc_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chunk_id"], ["doc_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_doc_embeddings"),
        sa.UniqueConstraint("chunk_id", name="uq_doc_embeddings_chunk_id"),
    )
    op.execute(
        f"ALTER TABLE doc_embeddings ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSION}) "
        f"USING embedding::vector({EMBEDDING_DIMENSION});"
    )
    op.create_index("ix_doc_embeddings_model", "doc_embeddings", ["model"], unique=False)
    op.create_index("ix_doc_embeddings_dim", "doc_embeddings", ["dim"], unique=False)
    op.execute(
        "CREATE INDEX ix_doc_embeddings_embedding_hnsw "
        "ON doc_embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_embeddings_embedding_hnsw;")
    op.drop_index("ix_doc_embeddings_dim", table_name="doc_embeddings")
    op.drop_index("ix_doc_embeddings_model", table_name="doc_embeddings")
    op.drop_table("doc_embeddings")

    op.drop_index("ix_doc_chunks_content_hash", table_name="doc_chunks")
    op.drop_index("ix_doc_chunks_chunk_index", table_name="doc_chunks")
    op.drop_index("ix_doc_chunks_doc_id", table_name="doc_chunks")
    op.drop_table("doc_chunks")

    op.drop_constraint("ck_documents_embedding_status", "documents", type_="check")
    op.drop_index("ix_documents_text_hash", table_name="documents")
    op.drop_index("ix_documents_embedding_status", table_name="documents")
    op.drop_column("documents", "embedding_updated_at")
    op.drop_column("documents", "embedding_error")
    op.drop_column("documents", "embedding_dim")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "embedding_status")
    op.drop_column("documents", "text_hash")
