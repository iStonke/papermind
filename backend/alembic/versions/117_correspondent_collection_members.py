"""Sammlungen als Behälter: Organisationen und Personen dürfen einer Sammlung angehören.

Bisher durften nur Personen ein ``parent_id`` tragen (Person → Organisation).
Neu: Sammlung → Organisation → Person (höchstens drei Ebenen). Die erlaubten
Kombinationen prüft die Service-Schicht; der CHECK sichert nur ab, dass
Sammlungen und Einträge ohne Typ selbst keinen übergeordneten Eintrag haben.

Revision ID: 117_correspondent_collections
Revises: 116_correspondent_relations
"""

from typing import Sequence, Union

from alembic import op


revision: str = "117_correspondent_collections"
down_revision: Union[str, None] = "116_correspondent_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_correspondents_parent_only_person", "correspondents", type_="check")
    op.create_check_constraint(
        "ck_correspondents_parent_kind",
        "correspondents",
        "parent_id IS NULL OR kind IN ('person', 'organization')",
    )


def downgrade() -> None:
    # Zurück zur Zwei-Ebenen-Regel: Organisationen verlieren ihre Sammlung.
    op.execute("UPDATE correspondents SET parent_id = NULL WHERE parent_id IS NOT NULL AND kind <> 'person'")
    op.execute(
        "UPDATE correspondents c SET parent_id = NULL FROM correspondents p "
        "WHERE c.parent_id = p.id AND p.kind <> 'organization'"
    )
    op.drop_constraint("ck_correspondents_parent_kind", "correspondents", type_="check")
    op.create_check_constraint(
        "ck_correspondents_parent_only_person",
        "correspondents",
        "parent_id IS NULL OR kind = 'person'",
    )
