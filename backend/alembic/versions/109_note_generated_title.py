"""Persist the origin of suggested note titles."""
from alembic import op
import sqlalchemy as sa
revision = '109_note_generated_title'
down_revision = '108_note_learn_highlight'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('note', sa.Column('title_is_generated', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('note', 'title_is_generated')
