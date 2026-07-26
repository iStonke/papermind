import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from app.worker import main as worker_main


class WorkerHealthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_last_at = worker_main._worker_health_last_at
        self.original_executor = worker_main._backup_executor
        self.original_future = worker_main._backup_future
        worker_main._worker_health_last_at = 0.0
        worker_main._backup_executor = None
        worker_main._backup_future = None

    def tearDown(self) -> None:
        executor = worker_main._backup_executor
        if executor is not None:
            executor.shutdown(wait=True)
        worker_main._worker_health_last_at = self.original_last_at
        worker_main._backup_executor = self.original_executor
        worker_main._backup_future = self.original_future

    def test_heartbeat_is_atomic_json_with_current_state(self) -> None:
        with TemporaryDirectory() as directory:
            target = Path(directory) / "worker-health.json"
            settings = SimpleNamespace(
                worker_health_path=str(target),
                worker_health_interval_seconds=1,
            )
            with mock.patch.object(worker_main, "settings", settings):
                worker_main._touch_worker_health(state="ocr", force=True)

            payload = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(payload["worker_id"], worker_main.WORKER_ID)
        self.assertEqual(payload["state"], "ocr")
        self.assertIsNone(payload["job_id"])
        self.assertIsInstance(payload["updated_at"], float)

    def test_scheduled_backup_is_not_submitted_twice_while_running(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def blocking_backup(*, kind: str) -> None:
            self.assertEqual(kind, "scheduled")
            started.set()
            release.wait(timeout=5)

        with mock.patch("app.services.backup.run_backup_in_background", side_effect=blocking_backup):
            self.assertTrue(worker_main._submit_scheduled_backup())
            self.assertTrue(started.wait(timeout=2))
            self.assertFalse(worker_main._submit_scheduled_backup())
            release.set()
            worker_main._backup_future.result(timeout=2)


if __name__ == "__main__":
    unittest.main()
