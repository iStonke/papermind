import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.observability import install_slow_query_logging

logger = logging.getLogger("papermind.db")
settings = get_settings()

# Superuser-Engine: Migrationen + Worker/System (umgeht Row-Level Security bewusst).
engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# App-Engine: nicht-privilegierte Rolle für Web-Requests. Row-Level Security ist
# hier aktiv; der Owner wird pro Request über die Session-Variable app.owner_id
# gesetzt (siehe app/core/deps.py).
_app_url = settings.sqlalchemy_app_database_url
if not settings.app_database_url:
    logger.warning(
        "APP_DATABASE_URL ist nicht gesetzt – Web-Requests laufen über die "
        "Superuser-Verbindung und Row-Level Security ist UNWIRKSAM. Für die "
        "Pro-Benutzer-Absicherung bitte APP_DATABASE_URL konfigurieren."
    )
app_engine = create_engine(
    _app_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
)
AppSessionLocal = sessionmaker(bind=app_engine, autocommit=False, autoflush=False)


@event.listens_for(app_engine, "checkout")
def _reset_owner_on_checkout(dbapi_conn, connection_record, connection_proxy) -> None:
    """Jede aus dem Pool geliehene Verbindung startet ohne gesetzten Owner, damit
    kein Owner aus einem vorherigen Request übernommen wird (fail-closed)."""
    try:
        with dbapi_conn.cursor() as cur:
            cur.execute("RESET app.owner_id")
    except Exception:  # noqa: BLE001 - darf den Checkout nie blockieren
        logger.exception("could not reset app.owner_id on checkout")


@event.listens_for(AppSessionLocal, "after_begin")
def _apply_owner_on_begin(session, transaction, connection) -> None:
    """Setzt app.owner_id für JEDE Transaktion der App-Session neu (transaktions-
    lokal). Quelle: session.info['owner_id'] (in app/core/deps.py gesetzt). So
    überlebt die Owner-Bindung den Connection-Wechsel nach commit()/rollback –
    sonst liefe z. B. der Post-Commit-Refresh wegen RESET-on-checkout leer und die
    RLS-USING-Policy fände die eigene Zeile nicht ('Could not refresh instance')."""
    owner = session.info.get("owner_id")
    if owner:
        connection.execute(
            text("SELECT set_config('app.owner_id', :owner_id, true)"),
            {"owner_id": str(owner)},
        )


# Worker-Engine: NOSUPERUSER + BYPASSRLS (System-Zugriff für Hintergrundjobs,
# aber ohne volle Superuser-Rechte). Fällt auf die Superuser-Verbindung zurück,
# wenn WORKER_DATABASE_URL nicht gesetzt ist.
if settings.worker_database_url:
    worker_engine = create_engine(
        settings.sqlalchemy_worker_database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
    )
    WorkerSessionLocal = sessionmaker(bind=worker_engine, autocommit=False, autoflush=False)
else:
    worker_engine = engine
    WorkerSessionLocal = SessionLocal

for observed_engine in {engine, app_engine, worker_engine}:
    install_slow_query_logging(observed_engine, settings.slow_query_threshold_ms)


def get_db() -> Generator[Session, None, None]:
    """Web-Request-Session über die RLS-Rolle."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()
