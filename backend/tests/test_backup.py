import unittest
from datetime import datetime, timedelta, timezone

from app.services.backup import (
    is_backup_due,
    mask_config,
    next_scheduled_slot,
    previous_scheduled_slot,
    select_old_backup_dirs,
)

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


class MaskConfigTest(unittest.TestCase):
    def test_password_masked(self) -> None:
        masked = mask_config({"nas_host": "192.168.178.73", "nas_password": "secret"})
        self.assertNotIn("nas_password", masked)
        self.assertTrue(masked["nas_password_set"])
        self.assertEqual(masked["nas_host"], "192.168.178.73")

    def test_empty_password_flag_false(self) -> None:
        self.assertFalse(mask_config({"nas_password": ""})["nas_password_set"])


if __name__ == "__main__":
    unittest.main()
