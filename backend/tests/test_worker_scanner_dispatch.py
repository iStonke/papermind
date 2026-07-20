import threading
import time
import unittest
from unittest import mock

from app.worker import main as worker_main


class ScannerDispatchLoopTest(unittest.TestCase):
    """Der Scanner-Dispatch läuft in einem eigenen Thread, damit UI-Scans nicht
    hinter langlaufender OCR/Bereinigung/LLM-Voranalyse im seriellen Haupt-Loop
    warten. Geprüft wird der Thread-Vertrag, nicht die Scanner-Hardware."""

    def _run_loop_briefly(self, drain_side_effect=None, iterations=3):
        stop_event = threading.Event()
        drain_calls = []

        def fake_drain():
            drain_calls.append(time.monotonic())
            if drain_side_effect is not None:
                drain_side_effect(len(drain_calls))
            if len(drain_calls) >= iterations:
                stop_event.set()

        with mock.patch.object(worker_main, "_sync_scanner_live_mode_config"), \
             mock.patch.object(worker_main, "_sync_scanner_scan_status"), \
             mock.patch.object(worker_main, "_drain_scanner_scan_commands", side_effect=fake_drain), \
             mock.patch.object(worker_main, "SCANNER_CONFIG_SYNC_INTERVAL_SECONDS", 0.01):
            thread = threading.Thread(
                target=worker_main._run_scanner_dispatch_loop,
                args=(stop_event,),
                daemon=True,
            )
            thread.start()
            thread.join(timeout=5)
        return thread, stop_event, drain_calls

    def test_loop_drains_repeatedly_and_stops_on_event(self) -> None:
        thread, stop_event, drain_calls = self._run_loop_briefly(iterations=3)
        self.assertFalse(thread.is_alive(), "Loop endet nach gesetztem Stop-Event")
        self.assertGreaterEqual(len(drain_calls), 3, "Dispatch läuft wiederholt, nicht nur einmal")

    def test_iteration_error_does_not_kill_thread(self) -> None:
        def raise_once(call_number):
            if call_number == 1:
                raise RuntimeError("transienter DB-Fehler")

        thread, _stop_event, drain_calls = self._run_loop_briefly(
            drain_side_effect=raise_once, iterations=3
        )
        self.assertFalse(thread.is_alive())
        # Nach dem Fehler in Iteration 1 muss der Thread weiterlaufen.
        self.assertGreaterEqual(len(drain_calls), 3, "Ein Fehler beendet den Thread nicht")


if __name__ == "__main__":
    unittest.main()
