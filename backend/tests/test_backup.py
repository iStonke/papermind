import unittest
import os
import tempfile
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.backup import BackupRestoreRequest
from app.services.backup import (
    BackupService,
    is_backup_due,
    mask_config,
    next_scheduled_slot,
    previous_scheduled_slot,
    select_gfs_backup_dirs,
    select_old_backup_dirs,
)
from app.services.backup_crypto import (
    backup_encryption_key,
    decrypt_file,
    decrypt_secret,
    encrypt_file,
    encrypt_secret,
    manifest_hmac,
)
from app.services.maintenance import is_maintenance_active, maintenance_marker_path, maintenance_mode

TZ = timezone(timedelta(hours=2))  # feste Zone für deterministische Tests


def _dt(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


class ScheduleDailyTest(unittest.TestCase):
    cfg = {"enabled": True, "frequency": "daily", "time": "03:00"}

    def test_previous_slot_after_time(self) -> None:
        slot = previous_scheduled_slot(self.cfg, now=_dt(2026, 6, 4, 5, 0))
        self.assertEqual(slot, _dt(2026, 6, 4, 3, 0))

    def test_previous_slot_before_time(self) -> None:
        slot = previous_scheduled_slot(self.cfg, now=_dt(2026, 6, 4, 1, 0))
        self.assertEqual(slot, _dt(2026, 6, 3, 3, 0))

    def test_next_slot(self) -> None:
        self.assertEqual(next_scheduled_slot(self.cfg, now=_dt(2026, 6, 4, 5, 0)), _dt(2026, 6, 5, 3, 0))

    def test_due_when_never_run(self) -> None:
        self.assertTrue(is_backup_due(self.cfg, now=_dt(2026, 6, 4, 5, 0), last_run_at=None))

    def test_not_due_when_already_ran_after_slot(self) -> None:
        self.assertFalse(is_backup_due(self.cfg, now=_dt(2026, 6, 4, 5, 0), last_run_at=_dt(2026, 6, 4, 4, 0)))

    def test_due_when_last_run_before_slot(self) -> None:
        self.assertTrue(is_backup_due(self.cfg, now=_dt(2026, 6, 4, 5, 0), last_run_at=_dt(2026, 6, 3, 3, 0)))

    def test_disabled_never_due(self) -> None:
        cfg = {**self.cfg, "enabled": False}
        self.assertFalse(is_backup_due(cfg, now=_dt(2026, 6, 4, 5, 0), last_run_at=None))


class ScheduleWeeklyTest(unittest.TestCase):
    # 2026-06-07 ist ein Sonntag (weekday=6)
    cfg = {"enabled": True, "frequency": "weekly", "time": "03:00", "weekday": 6}

    def test_previous_slot_is_last_sunday(self) -> None:
        slot = previous_scheduled_slot(self.cfg, now=_dt(2026, 6, 10, 12, 0))  # Mittwoch
        self.assertEqual(slot, _dt(2026, 6, 7, 3, 0))

    def test_next_slot_is_a_week_later(self) -> None:
        nxt = next_scheduled_slot(self.cfg, now=_dt(2026, 6, 10, 12, 0))
        self.assertEqual(nxt, _dt(2026, 6, 14, 3, 0))


class RetentionTest(unittest.TestCase):
    def test_keeps_newest_n(self) -> None:
        names = ["2026-06-01_030000", "2026-06-03_030000", "2026-06-02_030000", "junk", "2026-06-04_030000"]
        old = select_old_backup_dirs(names, retention=2)
        self.assertEqual(sorted(old), ["2026-06-01_030000", "2026-06-02_030000"])

    def test_ignores_invalid_names(self) -> None:
        self.assertEqual(select_old_backup_dirs(["nicht_passend", "auch_nicht"], retention=1), [])

    def test_gfs_keeps_daily_weekly_and_monthly_generations(self) -> None:
        names = [
            "2026-01-01_030000",
            "2026-01-02_030000",
            "2026-01-08_030000",
            "2026-02-01_030000",
            "2026-03-01_030000",
        ]
        old = select_gfs_backup_dirs(names, daily=2, weekly=2, monthly=3)
        self.assertEqual(sorted(old), ["2026-01-01_030000", "2026-01-02_030000"])


class BackupCryptoTest(unittest.TestCase):
    def test_streaming_encryption_roundtrip_and_tamper_detection(self) -> None:
        key = bytes(range(32))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            encrypted = root / "source.bin.enc"
            restored = root / "restored.bin"
            source.write_bytes(os.urandom(2 * 1024 * 1024 + 17))

            encrypt_file(source, encrypted, key)
            decrypt_file(encrypted, restored, key)
            self.assertEqual(restored.read_bytes(), source.read_bytes())

            payload = bytearray(encrypted.read_bytes())
            payload[len(payload) // 2] ^= 0x01
            encrypted.write_bytes(payload)
            with self.assertRaises(RuntimeError):
                decrypt_file(encrypted, restored, key)

    def test_secret_encryption_roundtrip(self) -> None:
        key = bytes(reversed(range(32)))
        encrypted = encrypt_secret("nas-secret", key)
        self.assertNotIn("nas-secret", encrypted)
        self.assertEqual(decrypt_secret(encrypted, key), "nas-secret")

    def test_key_loader_accepts_urlsafe_base64(self) -> None:
        import base64

        encoded = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
        with patch.dict(os.environ, {"BACKUP_ENCRYPTION_KEY": encoded}, clear=False):
            self.assertEqual(backup_encryption_key(), bytes(range(32)))

    def test_key_loader_reads_secret_file(self) -> None:
        import base64

        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "backup.key"
            key_file.write_text(base64.b64encode(bytes(range(32))).decode("ascii"), encoding="utf-8")
            with patch.dict(
                os.environ,
                {"BACKUP_ENCRYPTION_KEY": "", "BACKUP_ENCRYPTION_KEY_FILE": str(key_file)},
                clear=False,
            ):
                self.assertEqual(backup_encryption_key(), bytes(range(32)))

    def test_manifest_hmac_detects_metadata_tampering(self) -> None:
        key = bytes(range(32))
        manifest = {"format_version": 2, "encrypted": True, "database": {"counts": {"documents": 2}}}
        signature = manifest_hmac(manifest, key)
        manifest["database"]["counts"]["documents"] = 3
        self.assertNotEqual(signature, manifest_hmac(manifest, key))


class RestoreCommandTest(unittest.TestCase):
    def test_production_restore_resets_schema_and_uses_strict_restore(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with (
            patch.object(BackupService, "_database_url", return_value="postgresql://db/papermind"),
            patch.object(BackupService, "_terminate_other_connections") as terminate,
            patch.object(BackupService, "_pg_restore_to_url") as restore,
            patch("app.services.backup.subprocess.run", return_value=completed) as run,
        ):
            BackupService._pg_restore(Path("/tmp/database.dump"))

        terminate.assert_called_once_with("postgresql://db/papermind")
        schema_command = run.call_args.args[0]
        self.assertEqual(schema_command[0], "psql")
        self.assertIn("ON_ERROR_STOP=1", schema_command)
        self.assertIn("DROP SCHEMA public CASCADE", schema_command[-1])
        restore.assert_called_once_with(
            Path("/tmp/database.dump"),
            "postgresql://db/papermind",
            clean=False,
        )

    def test_encrypted_manifest_requires_signature(self) -> None:
        manifest = {"format_version": 2, "encrypted": True, "artifacts": []}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Manifest-Signatur"):
                BackupService(None)._download_manifest_artifacts(  # type: ignore[arg-type]
                    None,  # type: ignore[arg-type]
                    "2026-01-01_030000",
                    Path(directory),
                    manifest,
                )


class MaintenanceLeaseTest(unittest.TestCase):
    def test_context_sets_and_clears_shared_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"BACKUP_STATE_PATH": directory, "BACKUP_MAINTENANCE_LEASE_SECONDS": "30"},
            clear=False,
        ):
            self.assertFalse(is_maintenance_active())
            with maintenance_mode("test"):
                self.assertTrue(is_maintenance_active())
            self.assertFalse(is_maintenance_active())

    def test_stale_marker_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"BACKUP_STATE_PATH": directory, "BACKUP_MAINTENANCE_LEASE_SECONDS": "30"},
            clear=False,
        ):
            path = maintenance_marker_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"token": "stale", "updated_at": "2000-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            self.assertFalse(is_maintenance_active())
            self.assertFalse(path.exists())


class MaskConfigTest(unittest.TestCase):
    def test_password_masked(self) -> None:
        masked = mask_config({"nas_host": "192.168.178.73", "nas_password": "secret"})
        self.assertNotIn("nas_password", masked)
        self.assertTrue(masked["nas_password_set"])
        self.assertEqual(masked["nas_host"], "192.168.178.73")

    def test_empty_password_flag_false(self) -> None:
        self.assertFalse(mask_config({"nas_password": ""})["nas_password_set"])


class ArchiveCreatedAtTest(unittest.TestCase):
    def test_parses_timestamp_folder(self) -> None:
        dt = BackupService._archive_created_at("2026-06-04_222704")
        self.assertIsNotNone(dt)
        self.assertEqual((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second), (2026, 6, 4, 22, 27, 4))

    def test_returns_none_for_invalid(self) -> None:
        self.assertIsNone(BackupService._archive_created_at("nicht-ein-backup"))


class RestoreRequestValidationTest(unittest.TestCase):
    def test_accepts_valid_timestamp(self) -> None:
        self.assertEqual(BackupRestoreRequest(name="2026-06-04_222704").name, "2026-06-04_222704")

    def test_rejects_path_traversal_and_garbage(self) -> None:
        for bad in ["../etc", "2026-06-04", "2026-06-04_2227", "foo/bar", "2026-06-04_222704/.."]:
            with self.assertRaises(ValueError):
                BackupRestoreRequest(name=bad)


if __name__ == "__main__":
    unittest.main()
