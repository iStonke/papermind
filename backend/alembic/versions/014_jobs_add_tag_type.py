"""extend jobs type check constraint with TAG

Revision ID: 014_jobs_add_tag_type
Revises: 013_global_settings
Create Date: 2026-02-28 00:20:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_jobs_add_tag_type"
down_revision: Union[str, None] = "013_global_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_type", "jobs", "type IN ('OCR', 'INDEX', 'EMBED', 'TAG')")


def downgrade() -> None:
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_type", "jobs", "type IN ('OCR', 'INDEX', 'EMBED')")
