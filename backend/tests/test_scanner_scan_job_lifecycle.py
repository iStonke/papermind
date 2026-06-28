"""Integrationstest für den Scanner-Scan-Job-Lifecycle.

Treibt einen Job über die echten ``ScannerService``-Übergänge
queued → scanning → processing → ready (gegen die echte DB, Superuser-Session,
umgeht RLS für Setup/Assertions) und prüft zusätzlich die Fehler-/Aufräum-Pfade
(Timeout, Scanner offline, Cleanup, exakte Job-Zuordnung).

Wird übersprungen, wenn keine DB erreichbar ist – so bleibt der Test in reinen
Unit-Umgebungen grün, läuft aber in CI/lokal mit DB vollständig.
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.import_inbox import ImportInboxItem
from app.models.scanner import (
    ScannerDevice,
    ScannerDeviceRecipient,
    ScannerScanCommand,
    ScannerScanJob,
)
from app.models.user import User
from app.services.scanners import (
    SCAN_ERROR_SCANNER_OFFLINE,
    SCAN_ERROR_TIMEOUT,
    ScannerService,
)


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_db_reachable(), "Keine DB erreichbar – Lifecycle-Test übersprungen.")
class ScannerScanJobLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()  # Superuser → Setup/Assertions ohne RLS
        self.user = User(
            username=f"scanjob-{uuid.uuid4().hex[:8]}",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.flush()
        self.scanner = ScannerDevice(
            device_key=f"flatbed-{uuid.uuid4().hex[:8]}",
            name="Testscanner",
            enabled=True,
        )
        self.db.add(self.scanner)
        self.db.flush()
        self.db.add(ScannerDeviceRecipient(scanner_device_id=self.scanner.id, user_id=self.user.id))
        self.db.commit()
        self.service = ScannerService(self.db)

    def tearDown(self) -> None:
        # Aufräumen in FK-sicherer Reihenfolge (Commands referenzieren Jobs).
        self.db.rollback()
        self.db.execute(
            text("DELETE FROM scanner_scan_commands WHERE scanner_device_id = :sid"),
            {"sid": self.scanner.id},
        )
        self.db.execute(
            text("DELETE FROM scanner_scan_jobs WHERE scanner_device_id = :sid"),
            {"sid": self.scanner.id},
        )
        self.db.execute(
            text("DELETE FROM import_inbox_items WHERE scanner_device_id = :sid"),
            {"sid": self.scanner.id},
        )
        self.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": self.user.id})
        self.db.execute(text("DELETE FROM scanner_devices WHERE id = :id"), {"id": self.scanner.id})
        self.db.commit()
        self.db.close()

    def _job(self, job_id: uuid.UUID) -> ScannerScanJob:
        self.db.expire_all()
        return self.db.get(ScannerScanJob, job_id)

    def _make_inbox_item(self) -> ImportInboxItem:
        item = ImportInboxItem(
            owner_id=None,
            scanner_device_id=self.scanner.id,
            source_file_id=uuid.uuid4(),
            source_type="scanner",
            original_name="Scan.pdf",
            page_count=2,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def test_lifecycle_queued_to_ready(self) -> None:
        # queued: ein UI-Befehl legt Job + verknüpften Befehl an.
        response = self.service.enqueue_scan_command(self.scanner.id, "finish", requested_by=self.user.id)
        command = self.db.get(ScannerScanCommand, response.id)
        self.assertIsNotNone(command.scan_job_id)
        job_id = command.scan_job_id
        self.assertEqual(self._job(job_id).state, "queued")

        # scanning
        self.service.mark_scan_started(self.scanner.id)
        self.db.commit()
        job = self._job(job_id)
        self.assertEqual(job.state, "scanning")
        self.assertIsNotNone(job.started_at)

        # processing
        self.service.mark_scan_processing(self.scanner.id)
        self.db.commit()
        self.assertEqual(self._job(job_id).state, "processing")

        # ready – exakte Zuordnung über die Job-ID (wie vom Host-Dateinamen).
        item = self._make_inbox_item()
        self.service.mark_scan_ready(
            self.scanner.id,
            import_inbox_item_id=item.id,
            source_file_id=item.source_file_id,
            page_count=item.page_count,
            job_id=job_id,
        )
        self.db.commit()
        job = self._job(job_id)
        self.assertEqual(job.state, "ready")
        self.assertEqual(job.import_inbox_item_id, item.id)
        self.assertEqual(job.page_count, 2)
        self.assertIsNone(job.error)
        self.assertIsNone(job.error_kind)

    def test_ready_collapses_sibling_active_jobs(self) -> None:
        # Mehrseitige UI-Folge: mehrere Befehle = mehrere Jobs, aber nur EIN Beleg.
        page_job_id = self.service.enqueue_scan_command(
            self.scanner.id, "page", requested_by=self.user.id
        ).id
        finish_resp = self.service.enqueue_scan_command(self.scanner.id, "finish", requested_by=self.user.id)
        page_job = self.db.get(ScannerScanCommand, page_job_id).scan_job_id
        finish_job = self.db.get(ScannerScanCommand, finish_resp.id).scan_job_id

        item = self._make_inbox_item()
        self.service.mark_scan_ready(
            self.scanner.id,
            import_inbox_item_id=item.id,
            source_file_id=item.source_file_id,
            page_count=item.page_count,
            job_id=finish_job,
        )
        self.db.commit()
        # Der adressierte Job ist ready, der Geschwister-Job wurde entfernt.
        self.assertEqual(self._job(finish_job).state, "ready")
        self.assertIsNone(self._job(page_job))

    def test_expire_stale_active_job_becomes_timeout(self) -> None:
        job_id = self.service.enqueue_scan_command(self.scanner.id, "page", requested_by=self.user.id)
        job = self.db.get(ScannerScanCommand, job_id.id).scan_job_id
        # updated_at künstlich weit in die Vergangenheit setzen.
        self.db.query(ScannerScanJob).filter(ScannerScanJob.id == job).update(
            {ScannerScanJob.updated_at: datetime.now(timezone.utc) - timedelta(hours=1)}
        )
        self.db.commit()

        expired = self.service.expire_stale_scan_jobs(timeout_seconds=60)
        self.assertGreaterEqual(expired, 1)
        timed_out = self._job(job)
        self.assertEqual(timed_out.state, "error")
        self.assertEqual(timed_out.error_kind, SCAN_ERROR_TIMEOUT)

    def test_paused_processing_job_survives_but_stuck_scanning_times_out(self) -> None:
        # Realistische Mehrseiten-Pause: ein "processing"-Job (wartet auf die
        # nächste Seite) darf nach 5 min NICHT als Fehler gelten, ein in
        # "scanning" klebender Job (abgebrochener Lauf) hingegen schon.
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        processing = ScannerScanJob(
            scanner_device_id=self.scanner.id, command="page", state="processing"
        )
        scanning = ScannerScanJob(
            scanner_device_id=self.scanner.id, command="page", state="scanning"
        )
        self.db.add_all([processing, scanning])
        self.db.flush()
        self.db.query(ScannerScanJob).filter(
            ScannerScanJob.id.in_([processing.id, scanning.id])
        ).update({ScannerScanJob.updated_at: five_min_ago}, synchronize_session=False)
        self.db.commit()

        # Standard-Schwellen: scanning 180 s, processing 1800 s.
        self.service.expire_stale_scan_jobs()
        self.assertEqual(self._job(scanning.id).state, "error")
        self.assertEqual(self._job(scanning.id).error_kind, SCAN_ERROR_TIMEOUT)
        self.assertEqual(self._job(processing.id).state, "processing")

    def test_expired_command_marks_job_scanner_offline(self) -> None:
        response = self.service.enqueue_scan_command(self.scanner.id, "page", requested_by=self.user.id)
        command = self.db.get(ScannerScanCommand, response.id)
        job_id = command.scan_job_id
        # Befehl künstlich altern lassen, damit er als abgelaufen gilt.
        self.db.query(ScannerScanCommand).filter(ScannerScanCommand.id == command.id).update(
            {ScannerScanCommand.created_at: datetime.now(timezone.utc) - timedelta(hours=1)}
        )
        self.db.commit()

        claimed = self.service.claim_pending_scan_commands(self.scanner.id)
        self.assertEqual(claimed, [])  # abgelaufen → nicht mehr ausgeführt
        job = self._job(job_id)
        self.assertEqual(job.state, "error")
        self.assertEqual(job.error_kind, SCAN_ERROR_SCANNER_OFFLINE)

    def test_cleanup_removes_old_terminal_jobs(self) -> None:
        item = self._make_inbox_item()
        response = self.service.enqueue_scan_command(self.scanner.id, "finish", requested_by=self.user.id)
        job_id = self.db.get(ScannerScanCommand, response.id).scan_job_id
        self.service.mark_scan_ready(
            self.scanner.id,
            import_inbox_item_id=item.id,
            source_file_id=item.source_file_id,
            page_count=1,
            job_id=job_id,
        )
        self.db.commit()
        # finished_at künstlich altern lassen.
        self.db.query(ScannerScanJob).filter(ScannerScanJob.id == job_id).update(
            {ScannerScanJob.finished_at: datetime.now(timezone.utc) - timedelta(days=30)}
        )
        self.db.commit()

        removed = self.service.cleanup_old_scan_jobs(retention_seconds=3600)
        self.assertGreaterEqual(removed, 1)
        self.assertIsNone(self._job(job_id))


if __name__ == "__main__":
    unittest.main()
