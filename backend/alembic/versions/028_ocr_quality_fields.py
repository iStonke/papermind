"""add OCR quality fields

Revision ID: 028_ocr_quality_fields
Revises: 027_preserve_unassigned_tags
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_ocr_quality_fields"
down_revision: Union[str, None] = "027_preserve_unassigned_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ocr_quality_status", sa.String(length=16), nullable=True))
    op.add_column("documents", sa.Column("ocr_confidence_score", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("ocr_quality_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ocr_processing_seconds", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_documents_ocr_quality_status",
        "documents",
        "ocr_quality_status IS NULL OR ocr_quality_status IN ('good', 'warning', 'error')",
    )
    op.create_check_constraint(
        "ck_documents_ocr_confidence_score",
        "documents",
        "ocr_confidence_score IS NULL OR (ocr_confidence_score >= 0 AND ocr_confidence_score <= 100)",
    )
    op.create_index("ix_documents_ocr_quality_status", "documents", ["ocr_quality_status"], unique=False)
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
              jsonb_set(
                COALESCE(settings_json, '{}'::jsonb),
                '{ocr,use_unpaper}',
                'true'::jsonb,
                true
              ),
              '{ocr,language}',
              to_jsonb(
                CASE
                  WHEN COALESCE(settings_json->'ocr'->>'language', '') IN ('', 'deu')
                    THEN 'deu+eng'
                  ELSE settings_json->'ocr'->>'language'
                END
              ),
              true
            )
        WHERE id = 1;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_ocr_quality_status", table_name="documents")
    op.drop_constraint("ck_documents_ocr_confidence_score", "documents", type_="check")
    op.drop_constraint("ck_documents_ocr_quality_status", "documents", type_="check")
    op.drop_column("documents", "ocr_processing_seconds")
    op.drop_column("documents", "ocr_quality_message")
    op.drop_column("documents", "ocr_confidence_score")
    op.drop_column("documents", "ocr_quality_status")
