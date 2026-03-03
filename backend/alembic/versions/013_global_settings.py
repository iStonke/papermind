"""add global settings singleton table

Revision ID: 013_global_settings
Revises: 012_documents_dedupe_fields
Create Date: 2026-02-28 00:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "013_global_settings"
down_revision: Union[str, None] = "012_documents_dedupe_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULTS_SQL = """
jsonb_build_object(
  'ui', jsonb_build_object('theme_mode', 'system'),
  'documents', jsonb_build_object(
    'auto_ocr', true,
    'auto_tagging', false,
    'sort_order', 'newest'
  )
)
"""


def upgrade() -> None:
    op.create_table(
        "global_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_global_settings_singleton"),
        sa.PrimaryKeyConstraint("id", name="pk_global_settings"),
    )

    op.execute(
        f"""
        INSERT INTO global_settings (id, settings_json)
        VALUES (1, {DEFAULTS_SQL})
        ON CONFLICT (id) DO NOTHING;
        """
    )

    op.execute(
        f"""
        UPDATE global_settings
        SET settings_json = COALESCE(settings_json, '{{}}'::jsonb)
          || jsonb_build_object(
            'ui', ({DEFAULTS_SQL}->'ui') || COALESCE(settings_json->'ui', '{{}}'::jsonb),
            'documents', ({DEFAULTS_SQL}->'documents') || COALESCE(settings_json->'documents', '{{}}'::jsonb)
          )
        WHERE id = 1;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_global_settings_updated_at
        BEFORE UPDATE ON global_settings
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_global_settings_updated_at ON global_settings;")
    op.drop_table("global_settings")
