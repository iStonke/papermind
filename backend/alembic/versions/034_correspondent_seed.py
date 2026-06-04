"""seed AP10 correspondents with aliases and matchers

Revision ID: 034_correspondent_seed
Revises: 033_correspondents
Create Date: 2026-06-02 00:00:00.000000
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "034_correspondent_seed"
down_revision: Union[str, None] = "033_correspondents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (kanonischer Name, short_name, [Aliase])
# Jeder Alias dient der exakten Auflösung des rohen Absenders und wird zusätzlich
# als `contains`-Matcher (scope 'both') angelegt, damit er auch in Dateinamen und
# OCR-Text greift.
_CORRESPONDENT_SEED: list[tuple[str, str, list[str]]] = [
    ("Dataport AöR", "Dataport", ["Dataport"]),
    ("Vodafone GmbH", "Vodafone", ["Vodafone", "Red Plus", "GigaKombi"]),
    ("HUK-Coburg", "HUK", ["HUK", "HUK-Coburg", "Privathaftpflicht"]),
    ("Finanzamt Kiel", "FA Kiel", ["Finanzamt", "ELSTER", "Einkommensteuerbescheid", "Lohnsteuer"]),
    ("Landeshauptstadt Kiel", "LH Kiel", ["Landeshauptstadt Kiel"]),
    ("Hausverwaltung", "HV", ["Hausverwaltung", "Nebenkostenabrechnung"]),
    ("Techem", "Techem", ["Techem", "Heizkosten"]),
    ("Naturstrom AG", "Naturstrom", ["Naturstrom"]),
    ("SW Kiel Netz GmbH", "SW Kiel", ["SW Kiel", "Stadtwerke Kiel"]),
    ("Krankenkasse", "KK", ["Krankenkasse"]),
    ("Deutsche Rentenversicherung", "DRV", ["Deutsche Rentenversicherung", "DRV"]),
    ("VBL", "VBL", ["VBL"]),
    ("IHK Schleswig-Holstein", "IHK SH", ["IHK Schleswig-Holstein", "IHK SH"]),
    ("RBZ Wirtschaft Kiel", "RBZ Kiel", ["RBZ Wirtschaft Kiel"]),
    ("TH Lübeck", "TH HL", ["TH Lübeck", "FH Lübeck"]),
    ("Regionalschule Altenholz", "RS Altenh.", ["Regionalschule Altenholz"]),
    ("Timm-Kröger-Realschule", "TKR", ["Timm-Kröger"]),
    ("Reventlouschule Kiel", "Reventlou", ["Reventlouschule"]),
    ("Baltic Drive", "Baltic", ["Baltic Drive", "Heinzi's Fahrschule"]),
    ("KMTV", "KMTV", ["KMTV"]),
    ("Kieser Training", "Kieser", ["Kieser"]),
    ("McFIT", "McFIT", ["McFIT"]),
    ("Tanzschule Gemind", "Gemind", ["Tanzschule Gemind"]),
    ("mStore Kiel", "mStore", ["mStore"]),
]


def _tables():
    correspondents = sa.table(
        "correspondents",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.Text()),
        sa.column("short_name", sa.Text()),
    )
    aliases = sa.table(
        "correspondent_aliases",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("correspondent_id", postgresql.UUID(as_uuid=True)),
        sa.column("alias", sa.Text()),
    )
    matchers = sa.table(
        "correspondent_matchers",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("correspondent_id", postgresql.UUID(as_uuid=True)),
        sa.column("kind", sa.Text()),
        sa.column("pattern", sa.Text()),
        sa.column("scope", sa.Text()),
        sa.column("priority", sa.Integer()),
    )
    return correspondents, aliases, matchers


def upgrade() -> None:
    bind = op.get_bind()
    correspondents, aliases, matchers = _tables()

    for name, short_name, alias_list in _CORRESPONDENT_SEED:
        existing_id = bind.execute(
            sa.select(correspondents.c.id).where(sa.func.lower(correspondents.c.name) == name.lower())
        ).scalar_one_or_none()
        if existing_id is None:
            correspondent_id = uuid.uuid4()
            bind.execute(
                correspondents.insert().values(id=correspondent_id, name=name, short_name=short_name)
            )
        else:
            correspondent_id = existing_id

        for alias in alias_list:
            alias_exists = bind.execute(
                sa.select(aliases.c.id).where(
                    aliases.c.correspondent_id == correspondent_id,
                    sa.func.lower(aliases.c.alias) == alias.lower(),
                )
            ).scalar_one_or_none()
            if alias_exists is None:
                bind.execute(
                    aliases.insert().values(id=uuid.uuid4(), correspondent_id=correspondent_id, alias=alias)
                )

            matcher_exists = bind.execute(
                sa.select(matchers.c.id).where(
                    matchers.c.correspondent_id == correspondent_id,
                    sa.func.lower(matchers.c.pattern) == alias.lower(),
                    matchers.c.kind == "contains",
                )
            ).scalar_one_or_none()
            if matcher_exists is None:
                bind.execute(
                    matchers.insert().values(
                        id=uuid.uuid4(),
                        correspondent_id=correspondent_id,
                        kind="contains",
                        pattern=alias,
                        scope="both",
                        priority=100,
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()
    correspondents, _aliases, _matchers = _tables()
    names = [name for name, _short, _aliases_list in _CORRESPONDENT_SEED]
    # Aliase und Matcher hängen per ON DELETE CASCADE am Korrespondenten.
    bind.execute(correspondents.delete().where(correspondents.c.name.in_(names)))
