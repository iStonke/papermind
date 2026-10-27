"""Befund 4: Serverseitige Zeitlimits je Engine und ihre Abbildung auf HTTP 503."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.errors import install_exception_handlers, is_db_timeout
from app.db import session as db_session


def test_connect_args_skip_disabled_limits():
    assert db_session._timeout_connect_args(statement_timeout=0, lock_timeout=0) == {}
    assert db_session._timeout_connect_args(statement_timeout=120000, lock_timeout=0) == {
        "options": "-c statement_timeout=120000"
    }


def test_app_engine_sets_limits_but_superuser_engine_does_not():
    with db_session.app_engine.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar() == "2min"
        assert connection.execute(text("SHOW lock_timeout")).scalar() == "15s"
        assert connection.execute(text("SHOW idle_in_transaction_session_timeout")).scalar() == "10min"
    # Migrationen, Backup und Restore laufen über die Superuser-Engine ohne Limits.
    with db_session.engine.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar() == "0"
        assert connection.execute(text("SHOW lock_timeout")).scalar() == "0"


def test_lock_wait_fails_fast_with_recognizable_timeout():
    url = get_settings().sqlalchemy_database_url
    holder_engine = create_engine(url)
    waiter_engine = create_engine(url, connect_args=db_session._timeout_connect_args(lock_timeout=200))
    try:
        with holder_engine.connect() as holder, waiter_engine.connect() as waiter:
            holder.execute(text("SELECT pg_advisory_xact_lock(424242)"))
            with pytest.raises(OperationalError) as caught:
                waiter.execute(text("SELECT pg_advisory_xact_lock(424242)"))
            assert is_db_timeout(caught.value)
            holder.rollback()
    finally:
        holder_engine.dispose()
        waiter_engine.dispose()


class _FakeDriverError(Exception):
    def __init__(self, sqlstate):
        super().__init__("driver error")
        self.sqlstate = sqlstate


def _client_raising(sqlstate):
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise OperationalError("SELECT 1", {}, _FakeDriverError(sqlstate))

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("sqlstate", ["55P03", "57014"])
def test_db_timeout_becomes_retryable_503(sqlstate):
    response = _client_raising(sqlstate).get("/boom")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"]["code"] == "DATABASE_BUSY"


def test_other_operational_errors_stay_500():
    response = _client_raising("08006").get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
