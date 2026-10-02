import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from app.worker.ocr_isolation import OCRAborted, OCRChildFailed, OCRDeadlineExceeded, run_isolated


# Ziele müssen auf Modulebene liegen, damit der spawn-Kindprozess sie importieren kann.
def _double(value):
    return {"value": value * 2}


def _fail():
    raise ValueError("kaputtes PDF")


def _hang_with_grandchild(pid_file):
    child = subprocess.Popen(["sleep", "60"])
    Path(pid_file).write_text(str(child.pid))
    time.sleep(60)


def _crash():
    os._exit(9)


def _oom_killed():
    os.kill(os.getpid(), 9)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Zombies gelten noch als vorhanden, laufen aber nicht mehr.
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split()[2] != "Z"
    except FileNotFoundError:
        return True


def test_returns_result_from_child():
    assert run_isolated(_double, 21, deadline_seconds=60) == {"value": 42}


def test_child_error_is_reported_with_message():
    with pytest.raises(OCRChildFailed, match="kaputtes PDF"):
        run_isolated(_fail, deadline_seconds=60)


def test_child_crash_without_result_fails():
    with pytest.raises(OCRChildFailed, match="unerwartet beendet"):
        run_isolated(_crash, deadline_seconds=60)


def test_sigkilled_child_reports_probable_memory_shortage():
    with pytest.raises(OCRChildFailed, match="Arbeitsspeicher"):
        run_isolated(_oom_killed, deadline_seconds=60)


def test_deadline_kills_whole_process_group(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    started = time.monotonic()
    with pytest.raises(OCRDeadlineExceeded):
        run_isolated(_hang_with_grandchild, str(pid_file), deadline_seconds=3)
    assert time.monotonic() - started < 15
    grandchild = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while _pid_alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not _pid_alive(grandchild)


def test_abort_event_stops_child(tmp_path):
    abort = threading.Event()
    threading.Timer(1.0, abort.set).start()
    started = time.monotonic()
    with pytest.raises(OCRAborted):
        run_isolated(_hang_with_grandchild, str(tmp_path / "pid"), deadline_seconds=60, abort=abort)
    assert time.monotonic() - started < 15
