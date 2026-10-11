"""Pin notes to the top of their list, independent of favorites."""
from alembic import op
import sqlalchemy as sa
revision = '111_note_pinned'
down_revision = '110_note_text_no_image_names'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('note', sa.Column('pinned_at', sa.DateTime(timezone=True), nullable=True))
    # Bisher war „Anpinnen" in der Notizliste der Favoriten-Stern. Was dort
    # angepinnt war, bleibt angeheftet; ab jetzt sind beide unabhängig.
    op.execute("UPDATE note SET pinned_at = updated_at WHERE is_favorite AND NOT is_template")

def downgrade():
    op.drop_column('note', 'pinned_at')
