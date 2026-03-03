"""add document_files

Revision ID: 002_document_files
Revises: 001_initial
Create Date: 2026-02-26 23:00:00
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_document_files"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("file_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('original', 'ocr', 'preview_pdf', 'thumbnail')",
            name="ck_document_files_role",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_document_files"),
        sa.UniqueConstraint("document_id", "role", name="uq_document_files_document_role"),
    )

    op.create_index("ix_document_files_document_id", "document_files", ["document_id"], unique=False)
    op.create_index("ix_document_files_role", "document_files", ["role"], unique=False)

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, storage_key FROM documents WHERE storage_key IS NOT NULL")).fetchall()

    for row in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO document_files (id, document_id, role, file_key, filename, mime_type)
                VALUES (:id, :document_id, 'original', :file_key, 'original.pdf', 'application/pdf')
                ON CONFLICT (document_id, role) DO NOTHING
                """
            ),
            {
                "id": uuid.uuid4(),
                "document_id": row.id,
                "file_key": row.storage_key,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_document_files_role", table_name="document_files")
    op.drop_index("ix_document_files_document_id", table_name="document_files")
    op.drop_table("document_files")
