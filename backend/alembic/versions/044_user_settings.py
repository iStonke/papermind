"""per-user settings (ui.* overrides); system settings stay global.

Revision ID: 044_user_settings
Revises: 043_tag_policy_and_worker_role
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "044_user_settings"
down_revision: Union[str, None] = "043_tag_policy_and_worker_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("settings_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # RLS: jede Zeile gehört genau einem Benutzer (= app.owner_id).
    op.execute("ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS user_settings_owner_isolation ON user_settings")
    op.execute(
        f"""
        CREATE POLICY user_settings_owner_isolation ON user_settings
        USING (user_id = {_OWNER_EXPR})
        WITH CHECK (user_id = {_OWNER_EXPR})
        """
    )

    # Explizite Grants (Default-Privilegien aus 042/043 greifen i. d. R. bereits).
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON user_settings TO "{role}";
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_settings_owner_isolation ON user_settings")
    op.drop_table("user_settings")
