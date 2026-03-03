"""add ocr pipeline fields

Revision ID: 003_ocr_pipeline_fields
Revises: 002_document_files
Create Date: 2026-02-27 00:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_ocr_pipeline_fields"
down_revision: Union[str, None] = "002_document_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("text_content", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("text_source", sa.Text(), server_default=sa.text("'none'"), nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("ocr_status", sa.Text(), server_default=sa.text("'not_started'"), nullable=False),
    )

    op.create_check_constraint(
        "ck_documents_text_source",
        "documents",
        "text_source IN ('none', 'ocr')",
    )
    op.create_check_constraint(
        "ck_documents_ocr_status",
        "documents",
        "ocr_status IN ('not_started', 'queued', 'running', 'done', 'failed')",
    )

    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        CREATE UNIQUE INDEX uq_jobs_document_ocr_active
        ON jobs (document_id)
        WHERE type = 'OCR' AND status IN ('queued', 'running');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_jobs_document_ocr_active;")

    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "started_at")

    op.drop_constraint("ck_documents_ocr_status", "documents", type_="check")
    op.drop_constraint("ck_documents_text_source", "documents", type_="check")
    op.drop_column("documents", "ocr_status")
    op.drop_column("documents", "text_source")
    op.drop_column("documents", "text_content")
