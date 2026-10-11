"""Precompute and index chunk full-text vectors."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "112_chunk_search_vector"
down_revision = "111_note_pinned"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("doc_chunks", sa.Column("search_vector", TSVECTOR(),
        sa.Computed("to_tsvector('german'::regconfig, coalesce(text, ''))", persisted=True)))
    op.create_index("ix_doc_chunks_search_vector", "doc_chunks", ["search_vector"], postgresql_using="gin")


def downgrade():
    op.drop_index("ix_doc_chunks_search_vector", table_name="doc_chunks")
    op.drop_column("doc_chunks", "search_vector")
