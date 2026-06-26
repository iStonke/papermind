"""scanner-aware import inbox entries.

Revision ID: 053_scanner_import_inbox
Revises: 052_document_type_areas
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "053_scanner_import_inbox"
down_revision: Union[str, None] = "052_document_type_areas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "scanner_devices",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("device_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_key", name="uq_scanner_devices_device_key"),
    )
    op.create_index("ix_scanner_devices_enabled", "scanner_devices", ["enabled"], unique=False)

    op.create_table(
        "scanner_device_recipients",
        sa.Column("scanner_device_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scanner_device_id"], ["scanner_devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scanner_device_id", "user_id"),
        sa.UniqueConstraint("scanner_device_id", "user_id", name="uq_scanner_device_recipients_device_user"),
    )
    op.create_index(
        "ix_scanner_device_recipients_user_id",
        "scanner_device_recipients",
        ["user_id"],
        unique=False,
    )

    op.add_column("import_inbox_items", sa.Column("scanner_device_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "import_inbox_items",
        sa.Column("source_type", sa.Text(), server_default=sa.text("'shortcut'"), nullable=False),
    )
    op.create_foreign_key(
        "fk_import_inbox_items_scanner_device_id",
        "import_inbox_items",
        "scanner_devices",
        ["scanner_device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_import_inbox_items_scanner_device_id", "import_inbox_items", ["scanner_device_id"])
    op.create_index("ix_import_inbox_items_source_type", "import_inbox_items", ["source_type"])
    op.alter_column("import_inbox_items", "owner_id", existing_type=UUID(as_uuid=True), nullable=True)

    op.execute("ALTER TABLE import_inbox_items ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS import_inbox_items_owner_isolation ON import_inbox_items")
    op.execute(
        f"""
        CREATE POLICY import_inbox_items_owner_isolation ON import_inbox_items
        USING (
            owner_id = {_OWNER_EXPR}
            OR (
                owner_id IS NULL
                AND source_type = 'scanner'
                AND claimed_at IS NULL
                AND scanner_device_id IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM scanner_device_recipients r
                    JOIN scanner_devices d ON d.id = r.scanner_device_id
                    WHERE r.scanner_device_id = import_inbox_items.scanner_device_id
                      AND r.user_id = {_OWNER_EXPR}
                      AND d.enabled = true
                )
            )
        )
        WITH CHECK (
            owner_id = {_OWNER_EXPR}
            OR (
                owner_id IS NULL
                AND source_type = 'scanner'
                AND claimed_at IS NULL
                AND scanner_device_id IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM scanner_device_recipients r
                    JOIN scanner_devices d ON d.id = r.scanner_device_id
                    WHERE r.scanner_device_id = import_inbox_items.scanner_device_id
                      AND r.user_id = {_OWNER_EXPR}
                      AND d.enabled = true
                )
            )
        )
        """
    )
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE
                    ON scanner_devices, scanner_device_recipients, import_inbox_items
                    TO "{role}";
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    admin_id = bind.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true AND is_active = true ORDER BY created_at ASC LIMIT 1")
    ).scalar()
    if admin_id is not None:
        bind.execute(
            sa.text("UPDATE import_inbox_items SET owner_id = :owner_id WHERE owner_id IS NULL"),
            {"owner_id": admin_id},
        )

    op.execute("DROP POLICY IF EXISTS import_inbox_items_owner_isolation ON import_inbox_items")
    op.alter_column("import_inbox_items", "owner_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.execute(
        f"""
        CREATE POLICY import_inbox_items_owner_isolation ON import_inbox_items
        USING (owner_id = {_OWNER_EXPR})
        WITH CHECK (owner_id = {_OWNER_EXPR})
        """
    )
    op.drop_index("ix_import_inbox_items_source_type", table_name="import_inbox_items")
    op.drop_index("ix_import_inbox_items_scanner_device_id", table_name="import_inbox_items")
    op.drop_constraint("fk_import_inbox_items_scanner_device_id", "import_inbox_items", type_="foreignkey")
    op.drop_column("import_inbox_items", "source_type")
    op.drop_column("import_inbox_items", "scanner_device_id")
    op.drop_index("ix_scanner_device_recipients_user_id", table_name="scanner_device_recipients")
    op.drop_table("scanner_device_recipients")
    op.drop_index("ix_scanner_devices_enabled", table_name="scanner_devices")
    op.drop_table("scanner_devices")
