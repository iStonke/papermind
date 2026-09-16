import asyncio
import threading
import time

import pytest

from app.core.write_barrier import WriteBarrierMiddleware
from app.services.maintenance import (
    MaintenanceActive, acquire_write_activity, is_maintenance_active,
    maintenance_marker_path, maintenance_mode, write_activity,
)


@pytest.fixture(autouse=True)
def isolated_barrier(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_STATE_PATH", str(tmp_path))


def test_maintenance_drains_existing_writer_and_closes_admission():
    entered = threading.Event()
    finished = threading.Event()

    def backup():
        with maintenance_mode("test"):
            entered.set()
        finished.set()

    with write_activity():
        thread = threading.Thread(target=backup)
        thread.start()
        deadline = time.monotonic() + 2
        while not is_maintenance_active() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert is_maintenance_active()
        assert not entered.is_set()
        with pytest.raises(MaintenanceActive):
            acquire_write_activity()
        # Work already admitted can make nested service calls while draining.
        with write_activity():
            assert not entered.is_set()
    assert finished.wait(2)
    thread.join()
    acquire_write_activity().close()


def test_expired_or_deleted_marker_cannot_bypass_os_lock():
    with maintenance_mode("test"):
        maintenance_marker_path().unlink()
        with pytest.raises(MaintenanceActive):
            acquire_write_activity()
    acquire_write_activity().close()


def test_failed_maintenance_setup_releases_owner_and_marker(monkeypatch):
    from app.services import maintenance

    original = maintenance._open_lock

    def fail_barrier(name):
        if name == "write-barrier.lock":
            raise OSError("storage unavailable")
        return original(name)

    with monkeypatch.context() as patch:
        patch.setattr(maintenance, "_open_lock", fail_barrier)
        with pytest.raises(OSError, match="storage unavailable"):
            with maintenance_mode("failed setup"):
                pytest.fail("maintenance must not start")
    assert not is_maintenance_active()
    with maintenance_mode("retry"):
        assert is_maintenance_active()


@pytest.mark.parametrize("method,holds_after_headers", [("POST", True), ("GET", False)])
def test_http_barrier_drains_writes_but_not_idle_get_streams(method, holds_after_headers):
    async def scenario():
        headers_sent = asyncio.Event()
        finish_response = asyncio.Event()
        entered = threading.Event()

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            headers_sent.set()
            await finish_response.wait()
            await send({"type": "http.response.body", "body": b""})

        async def send(message):
            pass

        def backup():
            with maintenance_mode("http-test"):
                entered.set()

        task = asyncio.create_task(WriteBarrierMiddleware(app)(
            {"type": "http", "path": "/api/test", "method": method}, None, send,
        ))
        await headers_sent.wait()
        thread = threading.Thread(target=backup)
        thread.start()
        await asyncio.sleep(0.15)
        if holds_after_headers:
            assert not entered.is_set()
        else:
            assert entered.is_set()
        finish_response.set()
        await task
        await asyncio.to_thread(thread.join, 2)
        assert entered.is_set()

    asyncio.run(scenario())
