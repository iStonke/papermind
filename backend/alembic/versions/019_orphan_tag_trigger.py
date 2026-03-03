"""auto-remove orphan tags when last document relation is deleted

Revision ID: 019_orphan_tag_trigger
Revises: 018_settings_ui_filename_drawer
Create Date: 2026-02-28 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "019_orphan_tag_trigger"
down_revision: Union[str, None] = "018_settings_ui_filename_drawer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One-time cleanup for already orphaned tags.
    op.execute(
        """
        DELETE FROM tags t
        WHERE NOT EXISTS (
            SELECT 1
            FROM document_tags dt
            WHERE dt.tag_id = t.id
        )
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION delete_orphan_tag_after_document_tag_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            DELETE FROM tags t
            WHERE t.id = OLD.tag_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM document_tags dt
                  WHERE dt.tag_id = OLD.tag_id
              );
            RETURN NULL;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_delete_orphan_tag_after_document_tag_delete
        AFTER DELETE ON document_tags
        FOR EACH ROW
        EXECUTE FUNCTION delete_orphan_tag_after_document_tag_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_delete_orphan_tag_after_document_tag_delete ON document_tags;")
    op.execute("DROP FUNCTION IF EXISTS delete_orphan_tag_after_document_tag_delete();")

