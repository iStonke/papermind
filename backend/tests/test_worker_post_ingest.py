import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from app.worker import main as worker_main


class PostIngestWorkTest(unittest.TestCase):
    """Die schwere Nachbearbeitung läuft außerhalb des seriellen Haupt-Loops.
    Bereinigung (schnell, sichtbar) und Voranalyse (langsam, LLM) laufen in
    getrennten Spuren, damit die langsame Analyse die Bereinigung der nächsten
    Seite nicht blockiert."""

    def setUp(self) -> None:
        self.calls = []
        self.calls_lock = threading.Lock()

        def record(name):
            def _fn(ids, owner):
                with self.calls_lock:
                    self.calls.append((name, tuple(ids)))
            return _fn

        self.enhance_patch = mock.patch.object(
            worker_main, "_enhance_scanner_import_sources", side_effect=record("enhance")
        )
        self.preanalyze_patch = mock.patch.object(
            worker_main, "_preanalyze_import_sources", side_effect=record("preanalyze")
        )
        self.enhance_patch.start()
        self.preanalyze_patch.start()
        self.addCleanup(self.enhance_patch.stop)
        self.addCleanup(self.preanalyze_patch.stop)

    def _recorded(self):
        with self.calls_lock:
            return list(self.calls)

    def test_inline_scanner_drop_cleans_before_preanalysis(self) -> None:
        with mock.patch.object(worker_main, "_cleanup_executor", None):
            worker_main._submit_post_ingest_work(["a", "b"], None, uuid.uuid4())
        self.assertEqual(
            self._recorded(),
            [("enhance", ("a", "b")), ("preanalyze", ("a", "b"))],
            "Bereinigung muss vor der Voranalyse laufen",
        )

    def test_inline_non_scanner_drop_skips_cleanup(self) -> None:
        with mock.patch.object(worker_main, "_cleanup_executor", None):
            worker_main._submit_post_ingest_work(["a"], None, None)
        self.assertEqual(self._recorded(), [("preanalyze", ("a",))])

    def test_submit_empty_is_noop(self) -> None:
        with mock.patch.object(worker_main, "_cleanup_executor", None):
            worker_main._submit_post_ingest_work([], None, uuid.uuid4())
        self.assertEqual(self._recorded(), [])

    def test_slow_preanalysis_does_not_block_next_cleanup(self) -> None:
        """Kerngarantie: hängt die Voranalyse der ersten Seite, muss die
        Bereinigung der zweiten Seite trotzdem laufen."""
        release_preanalysis = threading.Event()
        first_cleanup_done = threading.Event()
        second_cleanup_done = threading.Event()

        def blocking_preanalyze(ids, owner):
            with self.calls_lock:
                self.calls.append(("preanalyze", tuple(ids)))
            release_preanalysis.wait(timeout=5)

        def tracking_enhance(ids, owner):
            with self.calls_lock:
                self.calls.append(("enhance", tuple(ids)))
            if ids == ["p1"]:
                first_cleanup_done.set()
            elif ids == ["p2"]:
                second_cleanup_done.set()

        cleanup_ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-cleanup")
        preanalysis_ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preanalysis")
        self.addCleanup(cleanup_ex.shutdown, wait=False)
        self.addCleanup(preanalysis_ex.shutdown, wait=False)

        with mock.patch.object(worker_main, "_cleanup_executor", cleanup_ex), \
             mock.patch.object(worker_main, "_preanalysis_executor", preanalysis_ex), \
             mock.patch.object(worker_main, "_enhance_scanner_import_sources", side_effect=tracking_enhance), \
             mock.patch.object(worker_main, "_preanalyze_import_sources", side_effect=blocking_preanalyze):
            worker_main._submit_post_ingest_work(["p1"], None, uuid.uuid4())
            self.assertTrue(first_cleanup_done.wait(timeout=5), "erste Bereinigung läuft")
            # Zweite Seite, während die Voranalyse der ersten noch blockiert.
            worker_main._submit_post_ingest_work(["p2"], None, uuid.uuid4())
            self.assertTrue(
                second_cleanup_done.wait(timeout=5),
                "zweite Bereinigung läuft trotz hängender Voranalyse der ersten",
            )
            release_preanalysis.set()

        names = [c[0] for c in self._recorded()]
        self.assertEqual(names.count("enhance"), 2)


if __name__ == "__main__":
    unittest.main()
