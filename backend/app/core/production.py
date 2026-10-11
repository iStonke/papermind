"""Fail closed when the production web role cannot enforce isolation."""
from sqlalchemy import text


def validate_production_security(settings, session_factory):
    if not settings.production_mode:
        return
    if not settings.auth_enabled or len(settings.auth_secret_key.strip()) < 32:
        raise RuntimeError("Production requires authentication and an AUTH_SECRET_KEY of at least 32 characters")
    if not settings.auth_cookie_secure:
        raise RuntimeError("Production requires secure authentication cookies")
    if not settings.app_database_url.strip() or not settings.worker_database_url.strip():
        raise RuntimeError("Production requires separate APP_DATABASE_URL and WORKER_DATABASE_URL roles")
    with session_factory() as db:
        role = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
        if role.rolsuper or role.rolbypassrls:
            raise RuntimeError("Production web role must not bypass row-level security")
        for table in ("documents", "doc_chunks", "note", "dossiers", "import_inbox_items"):
            if not db.scalar(text("SELECT row_security_active(:table)"), {"table": table}):
                raise RuntimeError(f"Production row-level security is inactive on {table}")
