"""Bounded document lanes: one OCR and one indexing/tagging operation at a time."""
import logging
from concurrent.futures import ThreadPoolExecutor

from app.services.maintenance import MaintenanceActive, acquire_write_activity, write_activity

logger = logging.getLogger("papermind.worker.dispatch")


class DocumentJobDispatcher:
    def __init__(self, claim, process):
        self.claim = claim
        self.process = process
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="document-job")
        self.futures = {}

    def _run(self, job, admission):
        with write_activity(admission=admission):
            self.process(job)

    def dispatch(self):
        submitted = False
        for lane, types in (("ocr", ("OCR",)), ("metadata", ("INDEX", "TAG"))):
            previous = self.futures.get(lane)
            if previous is not None:
                if not previous.done():
                    continue
                try:
                    previous.result()
                except Exception:
                    logger.exception("document lane failed lane=%s", lane)
                del self.futures[lane]
            try:
                admission = acquire_write_activity()
            except MaintenanceActive:
                return submitted
            try:
                job = self.claim(types)
                if job is None:
                    admission.close()
                    continue
                # Admission covers claim -> executor handoff -> publication.
                # A backup can never see an unprotected claimed job.
                self.futures[lane] = self.executor.submit(self._run, job, admission)
                submitted = True
            except BaseException:
                admission.close()
                raise
        return submitted

    @property
    def busy(self):
        return any(not future.done() for future in self.futures.values())

    def close(self):
        self.executor.shutdown(wait=True)
