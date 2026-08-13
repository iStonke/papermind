"""manual dossiers with grouped light-table items.

Revision ID: 067_dossier_light_table
Revises: 066_document_wiki_entries
Create Date: 2026-08-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "067_dossier_light_table"
down_revision: Union[str, None] = "066_document_wiki_entries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _grant(table: str) -> None:
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role}";
              END IF;
            END $$;
            """
        )


def _enable_child_rls(table: str, parent_column: str = "dossier_id", extra_check: str = "") -> None:
    owner_check = (
        f"EXISTS (SELECT 1 FROM dossiers ds WHERE ds.id = {table}.{parent_column} "
        f"AND ds.owner_id = {_OWNER_EXPR})"
    )
    condition = f"({owner_check}){extra_check}"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_owner_isolation ON {table} "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    _grant(table)


def upgrade() -> None:
    op.create_table(
        "dossiers",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("dossier_type", sa.Text(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('active', 'closed')", name="ck_dossiers_state"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dossiers_owner_id", "dossiers", ["owner_id"])
    op.create_index("ix_dossiers_owner_updated", "dossiers", ["owner_id", "updated_at"])
    op.create_index("ix_dossiers_owner_archived", "dossiers", ["owner_id", "archived_at"])

    op.create_table(
        "dossier_properties",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_number", sa.Float(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "value_type IN ('text', 'date', 'number', 'boolean')",
            name="ck_dossier_properties_value_type",
        ),
        sa.ForeignKeyConstraint(["dossier_id"], ["dossiers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dossier_properties_dossier_sort",
        "dossier_properties",
        ["dossier_id", "sort_order"],
    )

    op.create_table(
        "dossier_groups",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["dossier_id"], ["dossiers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dossier_groups_dossier_sort", "dossier_groups", ["dossier_id", "sort_order"])

    op.create_table(
        "dossier_items",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", UUID(as_uuid=True), nullable=True),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("note_title", sa.Text(), nullable=True),
        sa.Column("note_body", sa.Text(), nullable=True),
        sa.Column("note_color", sa.String(length=16), nullable=True),
        sa.Column("link_title", sa.Text(), nullable=True),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("link_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("item_type IN ('document', 'note', 'link')", name="ck_dossier_items_type"),
        sa.CheckConstraint(
            "(item_type = 'document' AND document_id IS NOT NULL) OR "
            "(item_type = 'note' AND document_id IS NULL) OR "
            "(item_type = 'link' AND document_id IS NULL AND link_url IS NOT NULL)",
            name="ck_dossier_items_payload",
        ),
        sa.ForeignKeyConstraint(["dossier_id"], ["dossiers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["dossier_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dossier_items_dossier_group_sort",
        "dossier_items",
        ["dossier_id", "group_id", "sort_order"],
    )
    op.create_index("ix_dossier_items_document_id", "dossier_items", ["document_id"])
    op.create_index(
        "uq_dossier_items_document_once",
        "dossier_items",
        ["dossier_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("item_type = 'document' AND document_id IS NOT NULL"),
    )

    op.execute("ALTER TABLE dossiers ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY dossiers_owner_isolation ON dossiers "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK (owner_id = {_OWNER_EXPR})"
    )
    _grant("dossiers")
    _enable_child_rls("dossier_properties")
    _enable_child_rls("dossier_groups")
    _enable_child_rls(
        "dossier_items",
        extra_check=(
            " AND (document_id IS NULL OR EXISTS (SELECT 1 FROM documents d "
            f"WHERE d.id = dossier_items.document_id AND d.owner_id = {_OWNER_EXPR}))"
        ),
    )

    for table in ("dossiers", "dossier_properties", "dossier_groups", "dossier_items"):
        op.execute(
            f"CREATE TRIGGER backup_source_dirty_{table} "
            f"AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
        )


def downgrade() -> None:
    for table in ("dossier_items", "dossier_groups", "dossier_properties", "dossiers"):
        op.execute(f"DROP TRIGGER backup_source_dirty_{table} ON {table}")
    for table in ("dossier_items", "dossier_groups", "dossier_properties", "dossiers"):
        op.execute(f"DROP POLICY {table}_owner_isolation ON {table}")
    op.drop_index("uq_dossier_items_document_once", table_name="dossier_items")
    op.drop_index("ix_dossier_items_document_id", table_name="dossier_items")
    op.drop_index("ix_dossier_items_dossier_group_sort", table_name="dossier_items")
    op.drop_table("dossier_items")
    op.drop_index("ix_dossier_groups_dossier_sort", table_name="dossier_groups")
    op.drop_table("dossier_groups")
    op.drop_index("ix_dossier_properties_dossier_sort", table_name="dossier_properties")
    op.drop_table("dossier_properties")
    op.drop_index("ix_dossiers_owner_archived", table_name="dossiers")
    op.drop_index("ix_dossiers_owner_updated", table_name="dossiers")
    op.drop_index("ix_dossiers_owner_id", table_name="dossiers")
    op.drop_table("dossiers")
