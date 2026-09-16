import threading
import time

from app.worker.document_dispatch import DocumentJobDispatcher


def test_slow_ocr_does_not_block_metadata_and_each_lane_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_STATE_PATH", str(tmp_path))
    release = threading.Event()
    ocr_started = threading.Event()
    metadata_done = threading.Event()
    claimed = []

    def claim(types):
        claimed.append(types)
        return types[0]

    def process(kind):
        if kind == "OCR":
            ocr_started.set()
            assert release.wait(3)
        else:
            metadata_done.set()

    dispatcher = DocumentJobDispatcher(claim, process)
    try:
        dispatcher.dispatch()
        assert ocr_started.wait(1)
        assert metadata_done.wait(1)
        deadline = time.monotonic() + 1
        while not dispatcher.futures["metadata"].done() and time.monotonic() < deadline:
            time.sleep(0.01)
        dispatcher.dispatch()
        assert claimed.count(("OCR",)) == 1
        assert claimed.count(("INDEX", "TAG")) == 2
        assert len(dispatcher.futures) <= 2
    finally:
        release.set()
        dispatcher.close()
