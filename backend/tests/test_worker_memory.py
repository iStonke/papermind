"""Befund 5: Kindprozesse zuerst opfern und Container-Speicher sichtbar machen."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core.oom import DISPOSABLE_OOM_SCORE_ADJ, prefer_oom_kill
from app.worker import main as worker_main


class PreferOomKillTest(unittest.TestCase):
    def test_writes_score_to_given_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "oom_score_adj"
            self.assertTrue(prefer_oom_kill(path=target))
            self.assertEqual(target.read_text(encoding="ascii").strip(), str(DISPOSABLE_OOM_SCORE_ADJ))

    def test_missing_proc_is_not_an_error(self) -> None:
        self.assertFalse(prefer_oom_kill(path=Path("/nonexistent-papermind/oom_score_adj")))

    @unittest.skipUnless(Path("/proc/self/oom_score_adj").exists(), "nur unter Linux")
    def test_unprivileged_child_raises_own_score_and_parent_keeps_its_own(self) -> None:
        parent_before = Path("/proc/self/oom_score_adj").read_text(encoding="ascii").strip()
        script = (
            "from app.core.oom import prefer_oom_kill;"
            "assert prefer_oom_kill();"
            "print(open('/proc/self/oom_score_adj').read().strip())"
        )
        child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
        self.assertEqual(child.stdout.strip(), str(DISPOSABLE_OOM_SCORE_ADJ))
        self.assertEqual(Path("/proc/self/oom_score_adj").read_text(encoding="ascii").strip(), parent_before)


class CgroupMemoryLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.original_oom_kills = worker_main._last_oom_kills
        worker_main._last_oom_kills = None

    def tearDown(self) -> None:
        worker_main._last_oom_kills = self.original_oom_kills
        self.directory.cleanup()

    def _write(self, *, current: int, anon: int, limit: str, oom_kills: int) -> None:
        (self.root / "memory.current").write_text(f"{current}\n")
        (self.root / "memory.max").write_text(f"{limit}\n")
        (self.root / "memory.stat").write_text(f"anon {anon}\nfile 123\n")
        (self.root / "memory.events").write_text(f"low 0\nhigh 0\nmax 4\noom 2\noom_kill {oom_kills}\n")

    def test_reads_cgroup_v2_files(self) -> None:
        self._write(current=900 * 2**20, anon=600 * 2**20, limit=str(2 * 2**30), oom_kills=1)
        self.assertEqual(
            worker_main._read_cgroup_memory(self.root),
            {"current": 900 * 2**20, "anon": 600 * 2**20, "limit": 2 * 2**30, "oom_kills": 1},
        )

    def test_unlimited_cgroup_and_missing_files(self) -> None:
        self.assertIsNone(worker_main._read_cgroup_memory(self.root))
        self._write(current=1, anon=1, limit="max", oom_kills=0)
        self.assertIsNone(worker_main._read_cgroup_memory(self.root)["limit"])

    def test_warns_on_new_oom_kill_and_memory_pressure(self) -> None:
        limit = 2 * 2**30
        with mock.patch.object(worker_main, "CGROUP_ROOT", self.root), \
             mock.patch.object(worker_main, "_read_process_rss_mb", return_value=300.0), \
             self.assertLogs("papermind.worker", level="INFO") as logs:
            self._write(current=limit // 2, anon=limit // 4, limit=str(limit), oom_kills=0)
            worker_main._log_worker_memory()
            self._write(current=limit, anon=int(limit * 0.9), limit=str(limit), oom_kills=2)
            worker_main._log_worker_memory()

        warnings = [line for line in logs.output if line.startswith("WARNING")]
        self.assertEqual(len(warnings), 2, logs.output)
        self.assertIn("oom_kills=2 new=2", warnings[0])
        self.assertIn("memory pressure", warnings[1])
        self.assertIn("cgroup_mb=1024.0", logs.output[0])


if __name__ == "__main__":
    unittest.main()
