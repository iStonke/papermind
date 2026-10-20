"""Small, source-scoped snapshots for analyses that outlive an HTTP request."""
import fcntl
import json
import os
import time
import uuid
from pathlib import Path


class ImportAnalysisJob:
    MAX_AGE_SECONDS = 15 * 60

    def __init__(self, path: Path):
        self.path = path
        self.lock = None
        self.job_id = str(uuid.uuid4())
        self.started_at = time.time()
        self.sequence = 0

    def read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or time.time() - float(data.get("updated_at", 0)) > self.MAX_AGE_SECONDS:
                return None
            return data
        except (OSError, ValueError, TypeError):
            return None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.path.with_suffix(".json.lock").open("a")
        try:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            self.close()
            return False

    def publish(self, result, *, pending, phase, worker_owned=False):
        self.sequence += 1
        result = {**result, "meta": {**(result.get("meta") or {}),
            "analysis_job_id": self.job_id, "analysis_sequence": self.sequence,
            "analysis_started_at": self.started_at,
            "analysis_pending": pending, "progress_phase": phase}}
        data = {"updated_at": time.time(), "worker_owned": worker_owned, "result": result}
        temporary = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return result

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None
