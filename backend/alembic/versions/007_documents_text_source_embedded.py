"""allow embedded text source for documents

Revision ID: 007_text_source_embedded
Revises: 006_fts_dual_lang_vector
Create Date: 2026-02-27 03:05:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_text_source_embedded"
down_revision: Union[str, None] = "006_fts_dual_lang_vector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_text_source", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_text_source",
        "documents",
        "text_source IN ('none', 'embedded', 'ocr')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_text_source", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_text_source",
        "documents",
        "text_source IN ('none', 'ocr')",
    )
