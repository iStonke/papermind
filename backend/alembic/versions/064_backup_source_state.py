"""skip unchanged scheduled backups

Revision ID: 064_backup_source_state
Revises: 063_backup_single_running
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "064_backup_source_state"
down_revision: Union[str, None] = "063_backup_single_running"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SOURCE_TABLES = (
    "alembic_version",
    "annotations",
    "correspondent_aliases",
    "correspondent_matchers",
    "correspondents",
    "doc_chunks",
    "document_files",
    "document_retention",
    "document_tags",
    "document_types",
    "documents",
    "global_settings",
    "import_inbox_items",
    "saved_searches",
    "scanner_device_recipients",
    "scanner_devices",
    "smart_folders",
    "tags",
    "user_settings",
    "users",
)


def upgrade() -> None:
    op.create_table(
        "backup_source_state",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("backed_up_generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_backup_source_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO backup_source_state (id, generation, backed_up_generation) VALUES (1, 1, 0)")
    op.execute(
        """
        CREATE FUNCTION mark_backup_source_dirty()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            UPDATE backup_source_state
            SET generation = generation + 1, last_changed_at = now()
            WHERE id = 1;
            RETURN NULL;
        END;
        $$
        """
    )
    for table in _SOURCE_TABLES:
        op.execute(
            f"CREATE TRIGGER backup_source_dirty_{table} "
            f"AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
        )

    op.drop_constraint("ck_backup_runs_status", "backup_runs", type_="check")
    op.create_check_constraint(
        "ck_backup_runs_status",
        "backup_runs",
        "status IN ('running', 'success', 'failed', 'skipped')",
    )


def downgrade() -> None:
    op.execute("UPDATE backup_runs SET status = 'success' WHERE status = 'skipped'")
    op.drop_constraint("ck_backup_runs_status", "backup_runs", type_="check")
    op.create_check_constraint(
        "ck_backup_runs_status",
        "backup_runs",
        "status IN ('running', 'success', 'failed')",
    )
    for table in _SOURCE_TABLES:
        op.execute(f"DROP TRIGGER backup_source_dirty_{table} ON {table}")
    op.execute("DROP FUNCTION mark_backup_source_dirty()")
    op.drop_table("backup_source_state")
