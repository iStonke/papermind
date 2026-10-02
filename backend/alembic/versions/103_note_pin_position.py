"""Persist free positions on the Gedanken canvas."""
from alembic import op
import sqlalchemy as sa
revision = "103_note_pin_position"
down_revision = "102_note_pin"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("note_pin", sa.Column("position_x", sa.Integer(), nullable=True))
    op.add_column("note_pin", sa.Column("position_y", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_note_pin_position", "note_pin", "(position_x IS NULL AND position_y IS NULL) OR (position_x IS NOT NULL AND position_y IS NOT NULL AND position_x BETWEEN 0 AND 100000 AND position_y BETWEEN 0 AND 100000)")

def downgrade():
    op.drop_constraint("ck_note_pin_position", "note_pin", type_="check")
    op.drop_column("note_pin", "position_y")
    op.drop_column("note_pin", "position_x")
