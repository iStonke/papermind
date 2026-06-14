"""scope import inbox items by owner and enable RLS.

Revision ID: 045_import_inbox_owner_rls
Revises: 044_user_settings
Create Date: 2026-06-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "045_import_inbox_owner_rls"
down_revision: Union[str, None] = "044_user_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("import_inbox_items", sa.Column("owner_id", UUID(as_uuid=True), nullable=True))

    admin_id = bind.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true AND is_active = true ORDER BY created_at ASC LIMIT 1")
    ).scalar()
    has_rows = bind.execute(sa.text("SELECT 1 FROM import_inbox_items LIMIT 1")).first() is not None
    if has_rows and admin_id is None:
        raise RuntimeError(
            "Migration 045 benötigt einen aktiven Admin als Eigentümer für vorhandene Import-Inbox-Einträge."
        )
    if admin_id is not None:
        bind.execute(
            sa.text("UPDATE import_inbox_items SET owner_id = :owner_id WHERE owner_id IS NULL"),
            {"owner_id": admin_id},
        )

    op.alter_column("import_inbox_items", "owner_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "fk_import_inbox_items_owner_id_users",
        "import_inbox_items",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_import_inbox_items_owner_id", "import_inbox_items", ["owner_id"])

    op.execute("ALTER TABLE import_inbox_items ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS import_inbox_items_owner_isolation ON import_inbox_items")
    op.execute(
        f"""
        CREATE POLICY import_inbox_items_owner_isolation ON import_inbox_items
        USING (owner_id = {_OWNER_EXPR})
        WITH CHECK (owner_id = {_OWNER_EXPR})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS import_inbox_items_owner_isolation ON import_inbox_items")
    op.execute("ALTER TABLE import_inbox_items DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_import_inbox_items_owner_id", table_name="import_inbox_items")
    op.drop_constraint("fk_import_inbox_items_owner_id_users", "import_inbox_items", type_="foreignkey")
    op.drop_column("import_inbox_items", "owner_id")
