"""add dedupe fields and indexes

Revision ID: 012_documents_dedupe_fields
Revises: 011_documents_display_name
Create Date: 2026-02-27 22:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012_documents_dedupe_fields"
down_revision: Union[str, None] = "011_documents_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("text_hash_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("text_simhash64", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("first_page_phash64", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("simhash_bucket1", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("simhash_bucket2", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("simhash_bucket3", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("simhash_bucket4", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("duplicate_of_doc_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("documents", sa.Column("duplicate_kind", sa.String(length=16), nullable=True))
    op.add_column("documents", sa.Column("duplicate_score", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("duplicate_checked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_documents_duplicate_of_doc_id_documents",
        "documents",
        "documents",
        ["duplicate_of_doc_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_documents_duplicate_kind",
        "documents",
        "duplicate_kind IS NULL OR duplicate_kind IN ('exact', 'text', 'image')",
    )
    op.create_index("ix_documents_duplicate_of_doc_id", "documents", ["duplicate_of_doc_id"], unique=False)
    op.create_index("ix_documents_text_simhash64", "documents", ["text_simhash64"], unique=False)
    op.create_index("ix_documents_first_page_phash64", "documents", ["first_page_phash64"], unique=False)
    op.create_index("ix_documents_simhash_bucket1", "documents", ["simhash_bucket1"], unique=False)
    op.create_index("ix_documents_simhash_bucket2", "documents", ["simhash_bucket2"], unique=False)
    op.create_index("ix_documents_simhash_bucket3", "documents", ["simhash_bucket3"], unique=False)
    op.create_index("ix_documents_simhash_bucket4", "documents", ["simhash_bucket4"], unique=False)

    op.create_index(
        "uq_documents_file_sha256_not_null",
        "documents",
        ["file_sha256"],
        unique=True,
        postgresql_where=sa.text("file_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_file_sha256_not_null", table_name="documents")
    op.drop_index("ix_documents_simhash_bucket4", table_name="documents")
    op.drop_index("ix_documents_simhash_bucket3", table_name="documents")
    op.drop_index("ix_documents_simhash_bucket2", table_name="documents")
    op.drop_index("ix_documents_simhash_bucket1", table_name="documents")
    op.drop_index("ix_documents_first_page_phash64", table_name="documents")
    op.drop_index("ix_documents_text_simhash64", table_name="documents")
    op.drop_index("ix_documents_duplicate_of_doc_id", table_name="documents")
    op.drop_constraint("ck_documents_duplicate_kind", "documents", type_="check")
    op.drop_constraint("fk_documents_duplicate_of_doc_id_documents", "documents", type_="foreignkey")

    op.drop_column("documents", "duplicate_checked_at")
    op.drop_column("documents", "duplicate_score")
    op.drop_column("documents", "duplicate_kind")
    op.drop_column("documents", "duplicate_of_doc_id")
    op.drop_column("documents", "simhash_bucket4")
    op.drop_column("documents", "simhash_bucket3")
    op.drop_column("documents", "simhash_bucket2")
    op.drop_column("documents", "simhash_bucket1")
    op.drop_column("documents", "first_page_phash64")
    op.drop_column("documents", "text_simhash64")
    op.drop_column("documents", "text_hash_sha256")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "file_sha256")
