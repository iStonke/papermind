"""Gedanken: owner-scoped plain-text inbox within note collections."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "102_note_pin"
down_revision = "101_learn_card_payload"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("note_pin",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", UUID(as_uuid=True), sa.ForeignKey("note_collection.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'sorted', 'archived')", name="ck_note_pin_status"),
        sa.CheckConstraint("length(trim(text)) > 0 AND length(text) <= 20000", name="ck_note_pin_text"),
    )
    op.create_index("ix_note_pin_owner_collection_created", "note_pin", ["owner_id", "collection_id", "created_at"])
    op.create_table("note_pin_tags",
        sa.Column("pin_id", UUID(as_uuid=True), sa.ForeignKey("note_pin.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    owner = "NULLIF(current_setting('app.owner_id', true), '')::uuid"
    op.execute("ALTER TABLE note_pin ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY note_pin_owner_isolation ON note_pin USING (owner_id = {owner}) WITH CHECK (owner_id = {owner})")
    op.execute("ALTER TABLE note_pin_tags ENABLE ROW LEVEL SECURITY")
    check = f"EXISTS (SELECT 1 FROM note_pin p WHERE p.id = pin_id AND p.owner_id = {owner}) AND EXISTS (SELECT 1 FROM tags t WHERE t.id = tag_id AND t.owner_id = {owner})"
    op.execute(f"CREATE POLICY note_pin_tags_owner_isolation ON note_pin_tags USING ({check}) WITH CHECK ({check})")
    for table in ("note_pin", "note_pin_tags"):
        for role in ("papermind_app", "papermind_worker"):
            op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {role}; END IF; END $$;")

def downgrade():
    op.drop_table("note_pin_tags")
    op.drop_table("note_pin")
