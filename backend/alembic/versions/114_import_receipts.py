"""Index durable import receipts for safe retries after a lost response."""
from alembic import op

revision = "114_import_receipts"
down_revision = "113_drop_note_favorite"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_import_receipt
        ON documents (owner_id,
          (flags['import_commit'] ->> 'request_id'),
          (flags['import_commit'] ->> 'client_document_id'))
        WHERE flags ? 'import_commit'""")


def downgrade():
    op.drop_index("uq_documents_import_receipt", table_name="documents")
