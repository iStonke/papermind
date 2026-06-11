"""harden document_tags RLS policy (enforce tag ownership too) and add a
dedicated NOSUPERUSER+BYPASSRLS worker role (least privilege for background jobs).

Revision ID: 043_tag_policy_and_worker_role
Revises: 042_row_level_security
Create Date: 2026-06-10 00:00:00.000000
"""

import os
from typing import Sequence, Union
from urllib.parse import unquote, urlsplit

from alembic import op

revision: str = "043_tag_policy_and_worker_role"
down_revision: Union[str, None] = "042_row_level_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _parse_role(env_var: str) -> tuple[str, str] | None:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return None
    parts = urlsplit(raw)
    username = unquote(parts.username or "")
    password = unquote(parts.password or "")
    if not username or not password:
        return None
    return username, password


def upgrade() -> None:
    # 1) document_tags: zusätzlich Tag-Eigentum erzwingen (nicht nur Dokument).
    doc_cond = (
        f"EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = document_tags.document_id AND d.owner_id = {_OWNER_EXPR})"
    )
    tag_cond = (
        f"EXISTS (SELECT 1 FROM tags t "
        f"WHERE t.id = document_tags.tag_id AND t.owner_id = {_OWNER_EXPR})"
    )
    cond = f"({doc_cond} AND {tag_cond})"
    op.execute("DROP POLICY IF EXISTS document_tags_owner_isolation ON document_tags")
    op.execute(
        f"CREATE POLICY document_tags_owner_isolation ON document_tags "
        f"USING ({cond}) WITH CHECK ({cond})"
    )

    # 2) Worker-Rolle (least privilege): NOSUPERUSER + BYPASSRLS. Nur wenn
    #    WORKER_DATABASE_URL gesetzt ist; sonst läuft der Worker weiter als Superuser.
    parsed = _parse_role("WORKER_DATABASE_URL")
    if parsed is None:
        return
    role, password = parsed
    role_q = f'"{role}"'
    pw_lit = password.replace("'", "''")
    db_name = op.get_bind().engine.url.database

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role_q} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"ALTER ROLE {role_q} WITH LOGIN NOSUPERUSER BYPASSRLS PASSWORD '{pw_lit}'")
    op.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {role_q}")
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


def downgrade() -> None:
    # document_tags-Policy auf die einfache (nur Dokument-)Variante zurücksetzen.
    doc_cond = (
        f"EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = document_tags.document_id AND d.owner_id = {_OWNER_EXPR})"
    )
    op.execute("DROP POLICY IF EXISTS document_tags_owner_isolation ON document_tags")
    op.execute(
        f"CREATE POLICY document_tags_owner_isolation ON document_tags "
        f"USING ({doc_cond}) WITH CHECK ({doc_cond})"
    )
    # Worker-Rolle bewusst nicht entfernen.
