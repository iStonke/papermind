"""Track committed source changes without a global writer lock.

Revision ID: 094_backup_change_journal
Revises: 093_note_collection
"""
from alembic import op

revision = "094_backup_change_journal"
down_revision = "093_note_collection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE backup_source_changes (
            transaction_id bigint PRIMARY KEY,
            changed_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION mark_backup_source_dirty()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO backup_source_changes (transaction_id)
            VALUES (txid_current()) ON CONFLICT DO NOTHING;
            RETURN NULL;
        END;
        $$
    """)


def downgrade() -> None:
    # Preserve dirtiness before returning to the old singleton counter.
    op.execute("""
        UPDATE backup_source_state
        SET generation = generation + (SELECT count(*) FROM backup_source_changes)
        WHERE id = 1
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION mark_backup_source_dirty()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE backup_source_state
            SET generation = generation + 1, last_changed_at = now() WHERE id = 1;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("DROP TABLE backup_source_changes")
