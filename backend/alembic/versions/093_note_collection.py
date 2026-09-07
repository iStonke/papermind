"""Sammlungen: oberste Notizen-Ebene (harter Kontext-Wechsel über Notizbüchern).

Eine Sammlung ist die *äußerste Schale* der Notizenverwaltung – wenige, grobe
Arbeitsbereiche (z. B. „Studium", „Arbeit"). Anders als Notizbücher (Ablage)
oder Tags (Querachse) ist sie eine **harte Partition**: eine echte Notiz gehört
zu genau **einer** Sammlung, und der Nutzer ist in der Oberfläche immer in genau
einer Sammlung („Space-Wechsel", kein „Alle über alle Sammlungen").

Modell: ``Sammlung → Notizbuch → Notiz`` (+ Tags quer). ``note.collection_id``
ist die Wahrheitsquelle; ``note_notebook.collection_id`` spiegelt sie (ein
Notizbuch lebt in genau einer Sammlung).

Bewusste Ausnahme: **Vorlagen sind sammlungsübergreifend**. Eine Vorlage/ein
Schnellblock soll in jeder Sammlung wiederverwendbar sein, trägt daher
``collection_id = NULL`` (global). Der partielle CHECK erzwingt die Zugehörigkeit
nur für Nicht-Vorlagen.

Bestand: pro Owner mit echten Notizen oder Notizbüchern wird eine Sammlung
„Allgemein" angelegt und alles dorthin gehängt. Neue/leere Owner erhalten ihre
erste Sammlung lazy im Service (``list_collections``), nicht über diese Migration.

Revision ID: 093_note_collection
Revises: 092_note_favorite
Create Date: 2026-09-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "093_note_collection"
down_revision: Union[str, None] = "092_note_favorite"
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


def upgrade() -> None:
    # --- 1) Tabelle note_collection (Vorlage: note_notebook / 091) -----------
    op.create_table(
        "note_collection",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_note_collection_owner_name"),
    )
    op.create_index("ix_note_collection_owner", "note_collection", ["owner_id", "position", "name"])

    # --- 2) Spalten (zunächst nullable für den Backfill) --------------------
    op.add_column("note", sa.Column("collection_id", UUID(as_uuid=True), nullable=True))
    op.add_column("note_notebook", sa.Column("collection_id", UUID(as_uuid=True), nullable=True))

    # --- 3) Backfill: je Owner mit echten Notizen ODER Notizbüchern eine
    #        Sammlung „Allgemein" anlegen und alles dorthin hängen. Vorlagen
    #        bleiben bewusst außen vor (collection_id NULL = global). ----------
    op.execute(
        """
        INSERT INTO note_collection (id, owner_id, name, position)
        SELECT gen_random_uuid(), o.owner_id, 'Allgemein', 0
        FROM (
            SELECT DISTINCT owner_id FROM note WHERE is_template = false
            UNION
            SELECT DISTINCT owner_id FROM note_notebook
        ) AS o
        """
    )
    op.execute(
        """
        UPDATE note AS n
        SET collection_id = c.id
        FROM note_collection AS c
        WHERE c.owner_id = n.owner_id
          AND c.name = 'Allgemein'
          AND n.is_template = false
          AND n.collection_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE note_notebook AS nb
        SET collection_id = c.id
        FROM note_collection AS c
        WHERE c.owner_id = nb.owner_id
          AND c.name = 'Allgemein'
          AND nb.collection_id IS NULL
        """
    )

    # --- 4) Invarianten festzurren ------------------------------------------
    # Notizbücher liegen IMMER in einer Sammlung.
    op.alter_column("note_notebook", "collection_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "fk_note_notebook_collection_id",
        "note_notebook",
        "note_collection",
        ["collection_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_note_notebook_collection", "note_notebook", ["owner_id", "collection_id"])
    # Notizbuch-Namen sind pro Sammlung eindeutig (nicht mehr pro Owner) – so kann
    # dasselbe Thema („Projekte") in mehreren Sammlungen existieren.
    op.drop_constraint("uq_note_notebook_owner_name", "note_notebook", type_="unique")
    op.create_unique_constraint(
        "uq_note_notebook_owner_collection_name",
        "note_notebook",
        ["owner_id", "collection_id", "name"],
    )

    # Echte Notizen brauchen eine Sammlung; Vorlagen dürfen NULL bleiben (global).
    op.create_foreign_key(
        "fk_note_collection_id",
        "note",
        "note_collection",
        ["collection_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_note_collection_required_unless_template",
        "note",
        "is_template OR collection_id IS NOT NULL",
    )
    op.create_index("ix_note_owner_collection", "note", ["owner_id", "collection_id"])

    # --- 5) RLS + Grants (Owner-Isolation wie note_notebook) ----------------
    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE note_collection ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_collection_owner_isolation ON note_collection "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_collection")


def downgrade() -> None:
    op.execute("DROP POLICY note_collection_owner_isolation ON note_collection")

    op.drop_index("ix_note_owner_collection", table_name="note")
    op.drop_constraint("ck_note_collection_required_unless_template", "note", type_="check")
    op.drop_constraint("fk_note_collection_id", "note", type_="foreignkey")
    op.drop_column("note", "collection_id")

    op.drop_constraint("uq_note_notebook_owner_collection_name", "note_notebook", type_="unique")
    op.create_unique_constraint(
        "uq_note_notebook_owner_name", "note_notebook", ["owner_id", "name"]
    )
    op.drop_index("ix_note_notebook_collection", table_name="note_notebook")
    op.drop_constraint("fk_note_notebook_collection_id", "note_notebook", type_="foreignkey")
    op.drop_column("note_notebook", "collection_id")

    op.drop_index("ix_note_collection_owner", table_name="note_collection")
    op.drop_table("note_collection")
