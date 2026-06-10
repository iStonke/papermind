"""per-user data isolation: add owner_id to documents, tags, document_types,
correspondents, saved_searches, smart_folders; scope uniqueness per owner.

Revision ID: 041_user_data_isolation
Revises: 040_user_avatar
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "041_user_data_isolation"
down_revision: Union[str, None] = "040_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tabellen mit Owner-scoped Namens-Eindeutigkeit (name -> (owner_id, name)).
_NAMED = [
    ("tags", "uq_tags_name", "ix_tags_name"),
    ("document_types", "uq_document_types_name", "ix_document_types_name"),
    ("correspondents", "uq_correspondents_name", "ix_correspondents_name"),
    ("saved_searches", "uq_saved_searches_name", "ix_saved_searches_name"),
    ("smart_folders", "uq_smart_folders_name", "ix_smart_folders_name"),
]
_ALL_TABLES = ["documents"] + [t[0] for t in _NAMED]


def upgrade() -> None:
    bind = op.get_bind()

    admin_id = bind.execute(
        sa.text("SELECT id FROM users WHERE is_admin = true ORDER BY created_at ASC LIMIT 1")
    ).scalar()

    # Guard: Es gibt Bestandsdaten, aber keinen Admin als Eigentümer.
    if admin_id is None:
        for table in _ALL_TABLES:
            has_rows = bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
            if has_rows:
                raise RuntimeError(
                    "Migration 041 benötigt einen Admin-Benutzer als Eigentümer für "
                    f"vorhandene Daten (Tabelle '{table}' ist nicht leer), es existiert "
                    "aber kein Admin. Bitte zuerst einen Admin anlegen."
                )

    # 1) Spalte nullable anlegen + Bestand auf den ersten Admin backfillen.
    for table in _ALL_TABLES:
        op.add_column(table, sa.Column("owner_id", UUID(as_uuid=True), nullable=True))
        if admin_id is not None:
            bind.execute(
                sa.text(f"UPDATE {table} SET owner_id = :oid WHERE owner_id IS NULL").bindparams(
                    oid=admin_id
                )
            )

    # 2) NOT NULL, FK, Index.
    for table in _ALL_TABLES:
        op.alter_column(table, "owner_id", existing_type=UUID(as_uuid=True), nullable=False)
        op.create_foreign_key(
            f"fk_{table}_owner_id_users", table, "users", ["owner_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])

    # 3) Namens-Eindeutigkeit auf Owner-Scope umstellen.
    for table, old_uq, old_ix in _NAMED:
        op.drop_constraint(old_uq, table, type_="unique")
        op.drop_index(old_ix, table_name=table)
        op.create_unique_constraint(f"uq_{table}_owner_name", table, ["owner_id", "name"])
        op.create_index(f"ix_{table}_owner_name", table, ["owner_id", "name"])


def downgrade() -> None:
    for table, old_uq, old_ix in _NAMED:
        op.drop_index(f"ix_{table}_owner_name", table_name=table)
        op.drop_constraint(f"uq_{table}_owner_name", table, type_="unique")
        op.create_unique_constraint(old_uq, table, ["name"])
        op.create_index(old_ix, table, ["name"])

    for table in _ALL_TABLES:
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"fk_{table}_owner_id_users", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
