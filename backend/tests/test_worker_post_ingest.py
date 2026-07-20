import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from app.worker import main as worker_main


class PostIngestWorkTest(unittest.TestCase):
    """Die schwere Nachbearbeitung (Bereinigung + Voranalyse) läuft außerhalb
    des seriellen Haupt-Loops, damit ein frischer Scan sofort ingestet wird."""

    def setUp(self) -> None:
        self.calls = []
        self.enhance_patch = mock.patch.object(
            worker_main,
            "_enhance_scanner_import_sources",
            side_effect=lambda ids, owner: self.calls.append(("enhance", tuple(ids))),
        )
        self.preanalyze_patch = mock.patch.object(
            worker_main,
            "_preanalyze_import_sources",
            side_effect=lambda ids, owner: self.calls.append(("preanalyze", tuple(ids))),
        )
        self.enhance_patch.start()
        self.preanalyze_patch.start()
        self.addCleanup(self.enhance_patch.stop)
        self.addCleanup(self.preanalyze_patch.stop)

    def test_scanner_drop_cleans_before_preanalysis(self) -> None:
        worker_main._run_post_ingest_work(["a", "b"], None, uuid.uuid4())
        self.assertEqual(
            self.calls,
            [("enhance", ("a", "b")), ("preanalyze", ("a", "b"))],
            "Bereinigung muss vor der Voranalyse laufen",
        )

    def test_non_scanner_drop_skips_cleanup(self) -> None:
        worker_main._run_post_ingest_work(["a"], None, None)
        self.assertEqual(self.calls, [("preanalyze", ("a",))])

    def test_submit_without_executor_runs_inline(self) -> None:
        with mock.patch.object(worker_main, "_post_ingest_executor", None):
            worker_main._submit_post_ingest_work(["a"], None, None)
        self.assertEqual(self.calls, [("preanalyze", ("a",))])

    def test_submit_empty_is_noop(self) -> None:
        with mock.patch.object(worker_main, "_post_ingest_executor", None):
            worker_main._submit_post_ingest_work([], None, uuid.uuid4())
        self.assertEqual(self.calls, [])

    def test_submit_with_executor_does_not_block_caller(self) -> None:
        release = threading.Event()
        done = threading.Event()

        def blocking_preanalyze(ids, owner):
            release.wait(timeout=5)
            self.calls.append(("preanalyze", tuple(ids)))
            done.set()

        executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown, wait=False)
        with mock.patch.object(worker_main, "_post_ingest_executor", executor), \
             mock.patch.object(worker_main, "_preanalyze_import_sources", side_effect=blocking_preanalyze):
            worker_main._submit_post_ingest_work(["a"], None, None)
            # Der Aufrufer (Haupt-Loop) darf nicht auf die schwere Arbeit warten.
            self.assertFalse(done.is_set(), "submit blockiert den Haupt-Loop nicht")
            release.set()
            self.assertTrue(done.wait(timeout=5), "Hintergrundarbeit läuft trotzdem")


if __name__ == "__main__":
    unittest.main()
