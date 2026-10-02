"""Separate Gedanken canvases within collections."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = "105_thought_rooms"
down_revision = "104_note_pin_color"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("thought_room",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", UUID(as_uuid=True), sa.ForeignKey("note_collection.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_thought_room_owner_collection", "thought_room", ["owner_id", "collection_id"])
    op.add_column("note_pin", sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("thought_room.id", ondelete="RESTRICT"), nullable=True))
    op.execute("INSERT INTO thought_room (id, owner_id, collection_id, title) SELECT gen_random_uuid(), owner_id, collection_id, 'Meine Gedanken' FROM note_pin GROUP BY owner_id, collection_id")
    op.execute("UPDATE note_pin p SET room_id = r.id FROM thought_room r WHERE p.owner_id = r.owner_id AND p.collection_id = r.collection_id")
    owner = "NULLIF(current_setting('app.owner_id', true), '')::uuid"
    op.execute("ALTER TABLE thought_room ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY thought_room_owner_isolation ON thought_room USING (owner_id = {owner}) WITH CHECK (owner_id = {owner})")
    for role in ("papermind_app", "papermind_worker"):
        op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN GRANT SELECT, INSERT, UPDATE, DELETE ON thought_room TO {role}; END IF; END $$;")

def downgrade():
    op.drop_column("note_pin", "room_id")
    op.drop_table("thought_room")
