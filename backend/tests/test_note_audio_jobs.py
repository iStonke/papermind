import io
import tempfile
import unittest
import uuid
import wave
from pathlib import Path

from app.services.note_audio_jobs import NoteAudioJobStore
from app.services.tts import merge_wav_bytes, split_speech_text


def _wav(frames: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(22050)
        target.writeframes(frames)
    return output.getvalue()


class NoteAudioJobStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = NoteAudioJobStore(Path(self.tempdir.name))
        self.owner = uuid.uuid4()
        self.note = uuid.uuid4()

    def tearDown(self):
        self.tempdir.cleanup()

    def create(self):
        return self.store.create(
            owner_id=self.owner,
            note_id=self.note,
            note_title="Meine Notiz",
            text="Ein kurzer Text.",
            voice="standard",
            language_mode="auto",
        )

    def test_queue_survives_new_store_instance_and_is_owner_scoped(self):
        created = self.create()
        reopened = NoteAudioJobStore(Path(self.tempdir.name))

        self.assertEqual(reopened.get(created["id"], owner_id=self.owner)["status"], "queued")
        self.assertEqual(reopened.get(created["id"], owner_id=self.owner)["language_mode"], "auto")
        self.assertIsNone(reopened.get(created["id"], owner_id=uuid.uuid4()))
        self.assertEqual(len(reopened.activity(self.owner)), 1)

    def test_claim_progress_finish_and_dismiss(self):
        created = self.create()
        claimed = self.store.claim_next("worker-test")
        self.assertEqual(claimed["id"], created["id"])
        self.assertEqual(claimed["status"], "running")

        incoming = self.store.output_path(created["id"]).with_suffix(".incoming")
        incoming.write_bytes(_wav(b"\x00\x00"))
        self.assertTrue(self.store.complete(created["id"], incoming))
        self.assertEqual(self.store.get(created["id"])["status"], "done")
        self.assertTrue(self.store.acknowledge_download(created["id"], self.owner))
        self.assertIsNone(self.store.get(created["id"]))
        self.assertFalse(self.store.output_path(created["id"]).exists())

    def test_download_acknowledgement_requires_owner_and_completed_job(self):
        created = self.create()
        self.assertFalse(self.store.acknowledge_download(created["id"], uuid.uuid4()))
        self.assertFalse(self.store.acknowledge_download(created["id"], self.owner))
        self.assertIsNotNone(self.store.get(created["id"]))

    def test_cancel_wins_over_publish(self):
        created = self.create()
        self.store.claim_next("worker-test")
        self.assertTrue(self.store.cancel(created["id"], self.owner))
        incoming = self.store.output_path(created["id"]).with_suffix(".incoming")
        incoming.write_bytes(_wav(b"\x00\x00"))

        self.assertFalse(self.store.complete(created["id"], incoming))
        self.assertIsNone(self.store.get(created["id"]))
        self.assertFalse(incoming.exists())

    def test_reclaims_running_job_after_worker_restart(self):
        created = self.create()
        self.store.claim_next("old-worker")
        self.assertEqual(self.store.reclaim_running(), 1)
        self.assertEqual(self.store.get(created["id"])["status"], "queued")


class NoteAudioWavTests(unittest.TestCase):
    def test_splits_long_text_and_merges_compatible_wav(self):
        chunks = split_speech_text("Erster Satz. " * 20, max_chars=60)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 60 for chunk in chunks))

        merged = merge_wav_bytes([_wav(b"\x01\x00"), _wav(b"\x02\x00")])
        with wave.open(io.BytesIO(merged), "rb") as source:
            self.assertEqual(source.getnframes(), 2)
            self.assertEqual(source.readframes(2), b"\x01\x00\x02\x00")


if __name__ == "__main__":
    unittest.main()
