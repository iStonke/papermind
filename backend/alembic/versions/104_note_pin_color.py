"""Persist Gedanken titlebar colors."""
from alembic import op
import sqlalchemy as sa
revision = "104_note_pin_color"
down_revision = "103_note_pin_position"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("note_pin", sa.Column("title_color", sa.String(7), nullable=True))

def downgrade():
    op.drop_column("note_pin", "title_color")
