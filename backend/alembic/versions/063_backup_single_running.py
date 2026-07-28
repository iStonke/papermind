"""allow only one running backup

Revision ID: 063_backup_single_running
Revises: 062_document_count_indexes
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "063_backup_single_running"
down_revision: Union[str, None] = "062_document_count_indexes"
branch_labels: Union[str, list[str], None] = None
depends_on: Union[str, list[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE backup_runs SET status = 'failed', finished_at = now(), "
        "error = COALESCE(error || ' ', '') || 'Durch Exklusivsperre bereinigt.' "
        "WHERE status = 'running'"
    )
    op.create_index(
        "uq_backup_runs_single_running",
        "backup_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_backup_runs_single_running", table_name="backup_runs")
