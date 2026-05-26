"""preserve unassigned tags

Revision ID: 027_preserve_unassigned_tags
Revises: 026_import_inbox
Create Date: 2026-05-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "027_preserve_unassigned_tags"
down_revision: Union[str, None] = "026_import_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_delete_orphan_tag_after_document_tag_delete ON document_tags;")
    op.execute("DROP FUNCTION IF EXISTS delete_orphan_tag_after_document_tag_delete();")


def downgrade() -> None:
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
