"""row-level security: dedicated non-privileged web role + RLS policies that
enforce per-user data isolation at the database layer (owner via app.owner_id).

Revision ID: 042_row_level_security
Revises: 041_user_data_isolation
Create Date: 2026-06-10 00:00:00.000000
"""

import os
from typing import Sequence, Union
from urllib.parse import unquote, urlsplit

from alembic import op

revision: str = "042_row_level_security"
down_revision: Union[str, None] = "041_user_data_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Owner-Spalte direkt auf der Tabelle.
_OWNER_TABLES = [
    "documents",
    "tags",
    "document_types",
    "correspondents",
    "saved_searches",
    "smart_folders",
]
# (Kind-Tabelle, Parent-Tabelle, FK-Spalte) — Owner erbt über den Parent.
_CHILD_TABLES = [
    ("document_files", "documents", "document_id"),
    ("doc_chunks", "documents", "doc_id"),
    ("document_tags", "documents", "document_id"),
    ("jobs", "documents", "document_id"),
    ("correspondent_aliases", "correspondents", "correspondent_id"),
    ("correspondent_matchers", "correspondents", "correspondent_id"),
]
_ALL_TABLES = _OWNER_TABLES + [c[0] for c in _CHILD_TABLES]

# SQL-Ausdruck des aktuellen Owners aus der Session-Variable (leer/fehlend -> NULL -> keine Zeilen).
_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _parse_app_role() -> tuple[str, str]:
    raw = os.environ.get("APP_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "Migration 042 benötigt APP_DATABASE_URL (Rolle für die Web-Verbindung). "
            "Bitte in der Umgebung setzen, z. B. "
            "postgresql+psycopg://papermind_app:<pw>@db:5432/<db>."
        )
    parts = urlsplit(raw)
    username = unquote(parts.username or "")
    password = unquote(parts.password or "")
    if not username or not password:
        raise RuntimeError("APP_DATABASE_URL muss Benutzername und Passwort enthalten.")
    return username, password


def upgrade() -> None:
    role, password = _parse_app_role()
    role_q = f'"{role}"'
    pw_lit = password.replace("'", "''")

    # 1) Rolle anlegen/aktualisieren (idempotent, nicht-privilegiert).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role_q} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"ALTER ROLE {role_q} WITH LOGIN NOSUPERUSER PASSWORD '{pw_lit}'")

    # 2) Rechte: nur DML, keine DDL-/Schemarechte.
    op.execute(f"GRANT CONNECT ON DATABASE {op.get_bind().engine.url.database} TO {role_q}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role_q}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role_q}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role_q}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role_q}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {role_q}"
    )

    # 3) RLS aktivieren + Policies (idempotent).
    for table in _ALL_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")

    for table in _OWNER_TABLES:
        op.execute(
            f"""
            CREATE POLICY {table}_owner_isolation ON {table}
            USING (owner_id = {_OWNER_EXPR})
            WITH CHECK (owner_id = {_OWNER_EXPR})
            """
        )

    for table, parent, fk in _CHILD_TABLES:
        cond = (
            f"EXISTS (SELECT 1 FROM {parent} p "
            f"WHERE p.id = {table}.{fk} AND p.owner_id = {_OWNER_EXPR})"
        )
        op.execute(
            f"""
            CREATE POLICY {table}_owner_isolation ON {table}
            USING ({cond})
            WITH CHECK ({cond})
            """
        )


def downgrade() -> None:
    for table in _ALL_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    # Rolle wird bewusst nicht gelöscht (könnte Objekte/Default-Privilegien besitzen).
