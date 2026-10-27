import threading
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from sqlalchemy.exc import OperationalError

from app.services.maintenance import MaintenanceActive
from app.worker import main as worker_main


def _db_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("server closed the connection unexpectedly"))


class MainLoopErrorGuardTest(unittest.TestCase):
    """Befund 1: Ein transienter DB-Fehler darf den Worker-Prozess nicht beenden."""

    def test_db_error_in_iteration_does_not_end_loop(self) -> None:
        stop_event = threading.Event()
        calls = []

        def iteration(_loop):
            calls.append(time.monotonic())
            if len(calls) <= 2:
                raise _db_error()
            stop_event.set()

        with mock.patch.object(worker_main, "_main_loop_error_backoff", return_value=0.0) as backoff, \
             mock.patch.object(worker_main, "_touch_worker_health"):
            thread = threading.Thread(
                target=worker_main._run_main_loop,
                args=(object(),),
                kwargs={"stop_event": stop_event, "iteration": iteration},
                daemon=True,
            )
            thread.start()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(calls), 3, "Nach zwei DB-Fehlern läuft der Loop weiter")
        self.assertEqual([call.args[0] for call in backoff.call_args_list], [1, 2])

    def test_failure_counter_resets_after_successful_iteration(self) -> None:
        stop_event = threading.Event()
        outcomes = iter([_db_error(), None, _db_error(), "stop"])

        def iteration(_loop):
            outcome = next(outcomes)
            if outcome == "stop":
                stop_event.set()
            elif outcome is not None:
                raise outcome

        with mock.patch.object(worker_main, "_main_loop_error_backoff", return_value=0.0) as backoff, \
             mock.patch.object(worker_main, "_touch_worker_health"):
            worker_main._run_main_loop(object(), stop_event=stop_event, iteration=iteration)

        self.assertEqual([call.args[0] for call in backoff.call_args_list], [1, 1])

    def test_backoff_grows_exponentially_and_is_capped(self) -> None:
        with mock.patch.object(worker_main, "settings", SimpleNamespace(worker_poll_interval_seconds=1)):
            delays = [worker_main._main_loop_error_backoff(n) for n in range(1, 9)]
        self.assertEqual(delays[:5], [1.0, 2.0, 4.0, 8.0, 16.0])
        self.assertTrue(all(delay == worker_main.MAIN_LOOP_ERROR_BACKOFF_MAX_SECONDS for delay in delays[5:]))

    def test_iteration_does_not_block_when_maintenance_starts(self) -> None:
        loop = SimpleNamespace(controlled_futures={}, document_dispatch=mock.Mock())
        with mock.patch.object(worker_main, "claim_queued", return_value=None), \
             mock.patch("app.services.maintenance.is_maintenance_active", return_value=False), \
             mock.patch("app.services.maintenance.acquire_write_activity", side_effect=MaintenanceActive("busy")), \
             mock.patch.object(worker_main, "_touch_worker_health") as health, \
             mock.patch.object(worker_main.time, "sleep") as sleep:
            worker_main._main_loop_iteration(loop)

        loop.document_dispatch.dispatch.assert_not_called()
        health.assert_called_with(state="maintenance")
        sleep.assert_called_once()


class WikiBackfillLaneTest(unittest.TestCase):
    """Befund 2: Ein Wiki-Backfill-Batch läuft in eigener Spur statt im Haupt-Loop."""

    def setUp(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()
        self.loop = SimpleNamespace(
            document_dispatch=SimpleNamespace(busy=False),
            wiki_executor=worker_main.ThreadPoolExecutor(max_workers=1),
            wiki_future=None,
        )
        self.admission = mock.Mock()

    def tearDown(self) -> None:
        self.release.set()
        self.loop.wiki_executor.shutdown(wait=True)

    def _patches(self, claim):
        def slow_batch(_run_id, _lease_token):
            self.started.set()
            self.release.wait(5)

        return (
            mock.patch("app.services.maintenance.acquire_write_activity", return_value=self.admission),
            mock.patch.object(worker_main, "_claim_next_wiki_backfill", side_effect=claim),
            mock.patch.object(worker_main, "_process_wiki_backfill", side_effect=slow_batch),
            mock.patch.object(worker_main, "_heartbeat_wiki_backfill", return_value=True),
        )

    def test_dispatch_returns_while_batch_runs_and_claims_only_once(self) -> None:
        claim = mock.Mock(return_value=(uuid.uuid4(), uuid.uuid4()))
        patches = self._patches(claim)
        with patches[0], patches[1], patches[2], patches[3]:
            started_at = time.monotonic()
            self.assertTrue(worker_main._dispatch_wiki_backfill(self.loop))
            self.assertLess(time.monotonic() - started_at, 1.0, "Dispatch blockiert den Haupt-Loop nicht")
            self.assertTrue(self.started.wait(2))
            self.assertFalse(worker_main._dispatch_wiki_backfill(self.loop), "kein zweiter Batch parallel")
            self.assertEqual(claim.call_count, 1)
            self.release.set()
            self.loop.wiki_future.result(timeout=5)
        self.admission.close.assert_called_once()

    def test_no_claim_while_document_lanes_are_busy(self) -> None:
        claim = mock.Mock(return_value=(uuid.uuid4(), uuid.uuid4()))
        self.loop.document_dispatch.busy = True
        patches = self._patches(claim)
        with patches[0], patches[1], patches[2], patches[3]:
            self.assertFalse(worker_main._dispatch_wiki_backfill(self.loop))
        claim.assert_not_called()

    def test_admission_released_when_nothing_to_claim(self) -> None:
        patches = self._patches(mock.Mock(return_value=None))
        with patches[0], patches[1], patches[2], patches[3]:
            self.assertFalse(worker_main._dispatch_wiki_backfill(self.loop))
        self.admission.close.assert_called_once()
        self.assertIsNone(self.loop.wiki_future)


class MainLoopWatchdogTest(unittest.TestCase):
    """Befund 3: Ein festhängender Haupt-Loop beendet den Prozess für den Docker-Neustart."""

    def setUp(self) -> None:
        self.original_tick = worker_main._main_loop_tick

    def tearDown(self) -> None:
        worker_main._main_loop_tick = self.original_tick

    def _run_watchdog(self, *, stall_seconds: float, keep_alive: bool, duration: float = 0.5):
        stop_event = threading.Event()
        exit_process = mock.Mock(side_effect=lambda _code: stop_event.set())
        worker_main._mark_main_loop_alive()
        thread = threading.Thread(
            target=worker_main._run_main_loop_watchdog,
            args=(stop_event,),
            kwargs={"stall_seconds": stall_seconds, "exit_process": exit_process},
            daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and not stop_event.is_set():
            if keep_alive:
                worker_main._mark_main_loop_alive()
            time.sleep(0.01)
        stop_event.set()
        thread.join(timeout=2)
        return exit_process

    def test_stalled_loop_exits_process(self) -> None:
        exit_process = self._run_watchdog(stall_seconds=0.1, keep_alive=False)
        exit_process.assert_called_once_with(worker_main.MAIN_LOOP_STALL_EXIT_CODE)

    def test_live_loop_is_left_alone(self) -> None:
        exit_process = self._run_watchdog(stall_seconds=0.2, keep_alive=True)
        exit_process.assert_not_called()

    def test_main_loop_marks_itself_alive_each_iteration(self) -> None:
        stop_event = threading.Event()
        worker_main._main_loop_tick = 0.0
        ticks = []

        def iteration(_loop):
            ticks.append(worker_main._main_loop_tick)
            if len(ticks) >= 2:
                stop_event.set()

        worker_main._run_main_loop(object(), stop_event=stop_event, iteration=iteration)
        self.assertTrue(all(tick > 0.0 for tick in ticks))
        self.assertLessEqual(ticks[0], ticks[1])


if __name__ == "__main__":
    unittest.main()
