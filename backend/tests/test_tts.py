import io
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from app.core.errors import APIError
from app.routers import tts as tts_router
from app.schemas.tts import SpeechRequest
from app.schemas.speech_options import SpeechOptions


def _test_wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(bytes([1, 0]) * 2205)
    return out.getvalue()

from app.services.tts import PiperTTSService, TTSUnavailableError, _speech_units, prepare_speech_text, segment_speech_text, split_speech_text


class _FakeVoice:
    def __init__(self, chunks=None, sample_rate=22050) -> None:
        self.synthesis_config = None
        self.chunks = chunks
        self.sample_rate = sample_rate
        self.texts = []

    def synthesize(self, text, *, syn_config):
        self.synthesis_config = syn_config
        self.texts.append(text)
        samples = self.chunks[text] if self.chunks is not None else [np.full(max(1, len(text)), 0.25, dtype=np.float32)]
        for audio in samples:
            yield SimpleNamespace(sample_rate=self.sample_rate, sample_width=2, sample_channels=1, audio_float_array=audio)


class PiperTTSServiceTest(unittest.TestCase):
    def test_synthesize_returns_valid_wav(self) -> None:
        service = PiperTTSService("/unused/test-model.onnx")
        with patch.object(service, "_get_voice", return_value=_FakeVoice()):
            audio = service.synthesize_wav("Hallo Welt")

        with wave.open(io.BytesIO(audio), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getframerate(), 22050)
            self.assertGreater(wav_file.getnframes(), 0)

    def test_emotional_preset_uses_expected_speaker(self) -> None:
        fake_voice = _FakeVoice()
        service = PiperTTSService("/unused/high.onnx", "/unused/emotional.onnx")
        with patch.object(service, "_get_voice", return_value=fake_voice) as get_voice:
            service.synthesize_wav("Gute Nacht", voice="sleepy")

        get_voice.assert_called_once_with("emotional")
        self.assertEqual(fake_voice.synthesis_config.speaker_id, 5)

    def test_missing_model_has_clear_error(self) -> None:
        service = PiperTTSService("/definitely/missing/model.onnx")
        with self.assertRaises(TTSUnavailableError):
            service.synthesize_wav("Hallo")

    def test_english_uses_dedicated_high_quality_model(self) -> None:
        service = PiperTTSService("/unused/de.onnx", "/unused/emotional.onnx", "/unused/en.onnx")
        with patch.object(service, "_get_voice", return_value=_FakeVoice()) as get_voice:
            service.synthesize_wav("This is an English sentence.", language="en")

        get_voice.assert_called_once_with("english")

    def test_sentence_and_paragraph_pauses_preserve_relative_loudness(self) -> None:
        fake = _FakeVoice({
            "A. B.": [np.full(100, 0.2, dtype=np.float32), np.full(100, 0.1, dtype=np.float32)],
            "C.": [np.full(100, 0.2, dtype=np.float32)],
        }, sample_rate=1000)
        service = PiperTTSService("/unused/high.onnx")
        with patch.object(service, "_get_voice", return_value=fake):
            audio = service.synthesize_wav("A. B.\nC.")
        with wave.open(io.BytesIO(audio)) as source:
            frames = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
        self.assertEqual(len(frames), 860)
        self.assertTrue(np.all(frames[100:280] == 0))
        self.assertTrue(np.all(frames[380:760] == 0))
        self.assertAlmostEqual(float(frames[0]) / float(frames[280]), 2.0, places=3)
        self.assertLess(int(np.max(np.abs(frames))), 32767)
        self.assertFalse(fake.synthesis_config.normalize_audio)

    def test_excessive_model_silence_is_bounded_without_cutting_speech(self) -> None:
        samples = np.concatenate([np.zeros(700), np.full(100, 0.2), np.zeros(900)])
        trimmed = PiperTTSService._trim_edge_silence(samples, 1000)
        self.assertEqual(len(trimmed), 180)  # speech plus 40 ms on each side
        np.testing.assert_array_equal(trimmed[40:140], samples[700:800])

    def test_empty_audio_has_clear_engine_error(self) -> None:
        fake = _FakeVoice({"Hallo": [np.zeros(100, dtype=np.float32)]})
        with patch.object(PiperTTSService, "_get_voice", return_value=fake):
            with self.assertRaises(TTSUnavailableError):
                PiperTTSService("/unused/high.onnx").synthesize_wav("Hallo")

    def test_abbreviation_expansion_is_only_for_spoken_german(self) -> None:
        text = "Die Abgabe erfolgt z. B. online, d. h. im Kurs.\nGgf. Rückfragen klären."
        spoken = prepare_speech_text(text)
        self.assertIn("zum Beispiel", spoken)
        self.assertIn("das heißt", spoken)
        self.assertIn("Gegebenenfalls", spoken)
        self.assertIn("\n", spoken)
        self.assertEqual(prepare_speech_text(text, language="en"), text)

    def test_sentence_final_abbreviation_keeps_the_sentence_boundary(self) -> None:
        self.assertEqual(prepare_speech_text("Notizen usw. Danach wird geprüft."), "Notizen und so weiter. Danach wird geprüft.")
        self.assertEqual(prepare_speech_text("Weitere Angaben usw."), "Weitere Angaben und so weiter.")
        self.assertIn("Unter Umständen", prepare_speech_text("U. U. wird später geprüft."))

    def test_titles_and_numbers_are_spoken_without_extra_stops(self) -> None:
        text = 'Dr. Müller bespricht die Nr. 3 (vgl. Abb. 2).'
        spoken = prepare_speech_text(text)
        self.assertEqual(spoken, 'Doktor Müller bespricht die Nummer 3 (vergleiche Abbildung 2).')
        self.assertEqual(prepare_speech_text('Dr. Smith discusses Nr. 3.', language='en'), 'Dr. Smith discusses Nr. 3.')


class SpeechSegmentationTest(unittest.TestCase):
    def test_german_quotes_keep_their_voice_before_an_english_sentence(self) -> None:
        for opener, closer in [('„', '“'), ('“', '”'), ('«', '»'), ('‚', '‘')]:
            with self.subTest(closer=closer):
                first = f'{opener}Die Prüfung wird im Kurs besprochen.{closer}'
                second = 'This is an English summary and it uses the corresponding voice.'
                segments = segment_speech_text(f'{first} {second}')
                self.assertEqual([s.language for s in segments], ['de', 'en'])
                self.assertEqual([s.text for s in segments], [first, second])

    def test_abbreviations_initials_ordinals_and_decimals_are_not_sentence_ends(self) -> None:
        text = 'Dr. A. Müller zeigt z. B. am 11. Oktober im 2. Semester die Nr. 3 mit 2,5 Punkten.'
        self.assertEqual(_speech_units(text), [(text, 0)])
        quoted = '„Hier endet der Satz.“ Danach beginnt der zweite Satz.'
        self.assertEqual(_speech_units(quoted), [('„Hier endet der Satz.“', 0), ('Danach beginnt der zweite Satz.', 0)])

    def test_paragraph_break_is_retained_when_the_voice_changes(self) -> None:
        german = 'Das ist ein deutscher Abschnitt und er wird vorgelesen.'
        english = 'This is an English section and it has its own paragraph.'
        for separator, expected in [(' ', False), ('\n', True)]:
            with self.subTest(separator=separator):
                segments = segment_speech_text(f'{german}{separator}{english}')
                self.assertEqual([s.language for s in segments], ['de', 'en'])
                self.assertEqual(segments[1].paragraph_break, expected)

    def test_forced_and_auto_modes_retain_paragraph_pause_at_chunk_limit(self) -> None:
        first = 'Das ist der erste Absatz.'
        second = 'Hier folgt der zweite Absatz.'
        for mode in ['auto', 'de']:
            segments = segment_speech_text(first + '\n' + second, mode=mode, max_chars=30)
            self.assertEqual([s.text for s in segments], [first, second])
            self.assertTrue(segments[1].paragraph_break)

    def test_long_sentences_split_at_clause_boundaries(self) -> None:
        text = 'Die Notizen behandeln zuerst die Grundlagen, danach folgen Beispiele, schließlich beginnt die Übung.'
        chunks = split_speech_text(text, max_chars=50)
        self.assertTrue(all(len(chunk) <= 50 for chunk in chunks))
        self.assertEqual(' '.join(chunks), text)
        self.assertTrue(chunks[0].endswith(','))

    def test_invalid_chunk_limit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_speech_text('Text', max_chars=0)

    def test_auto_mode_switches_between_german_and_english_sentences(self) -> None:
        segments = segment_speech_text(
            "Das ist ein deutscher Abschnitt und er wird mit Thorsten gesprochen. "
            "This is an English section and it uses the matching English voice. "
            "Danach wird der deutsche Text wieder mit Thorsten vorgelesen.",
            mode="auto",
        )

        self.assertEqual([segment.language for segment in segments], ["de", "en", "de"])

    def test_short_names_and_loanwords_do_not_trigger_voice_change(self) -> None:
        segments = segment_speech_text(
            "Das ist ein längerer deutscher Satz mit genügend eindeutigen Wörtern. OpenAI. "
            "Danach bleibt die ausgewählte deutsche Stimme weiterhin aktiv.",
            mode="auto",
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].language, "de")
        self.assertIn("OpenAI", segments[0].text)

    def test_forced_language_modes_skip_detection(self) -> None:
        english = segment_speech_text("Das ist deutscher Text.", mode="en")
        german = segment_speech_text("This is English text.", mode="de")

        self.assertTrue(all(segment.language == "en" for segment in english))
        self.assertTrue(all(segment.language == "de" for segment in german))

    def test_paragraph_boundaries_survive_both_language_modes_and_chunking(self) -> None:
        text = "Offene Fragen\nDie Prüfung wird im Kurs geklärt.\nWeitere Hinweise"
        for mode in ("auto", "de"):
            with self.subTest(mode=mode):
                self.assertEqual(segment_speech_text(text, mode=mode)[0].text, text)
        chunks = split_speech_text(text, max_chars=38)
        self.assertTrue(all(len(chunk) <= 38 for chunk in chunks))
        self.assertIn("\n", chunks[0])


class TTSEndpointTest(unittest.TestCase):
    def test_endpoint_returns_inline_audio(self) -> None:
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part"),
            patch.object(tts_router, "merge_speech_audio", return_value=_test_wav()),
        ):
            response = tts_router.synthesize_speech(SpeechRequest(text="  Hallo   Welt  "), MagicMock())

        self.assertEqual(response.media_type, "audio/wav")
        self.assertEqual(response.body, _test_wav())
        self.assertEqual(response.headers["x-speech-duration"], "0.100")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_endpoint_forwards_voice_preset(self) -> None:
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part") as synthesize,
            patch.object(tts_router, "merge_speech_audio", return_value=_test_wav()),
        ):
            tts_router.synthesize_speech(
                SpeechRequest(text="Hallo", voice="whisper"),
                MagicMock(),
            )

        synthesize.assert_called_once_with("Hallo", voice="whisper", language="de", options=SpeechOptions())

    def test_endpoint_uses_automatic_language_segments(self) -> None:
        text = (
            "Das ist ein deutscher Satz und er wird korrekt erkannt. "
            "This is an English sentence and it is detected correctly."
        )
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part") as synthesize,
            patch.object(tts_router, "merge_speech_audio", return_value=_test_wav()),
        ):
            tts_router.synthesize_speech(SpeechRequest(text=text, language_mode="auto"), MagicMock())

        self.assertEqual([call.kwargs["language"] for call in synthesize.call_args_list], ["de", "en"])

    def test_endpoint_maps_unavailable_engine_to_503(self) -> None:
        with (
            patch.object(
                tts_router.tts_service,
                "synthesize_wav",
                side_effect=TTSUnavailableError("missing"),
            ),
            self.assertRaises(APIError) as raised,
        ):
            tts_router.synthesize_speech(SpeechRequest(text="Hallo"), MagicMock())

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.code, "TTS_UNAVAILABLE")

    def test_configured_character_limit_is_enforced(self) -> None:
        settings = MagicMock(tts_max_chars=5)
        with (
            patch.object(tts_router, "get_settings", return_value=settings),
            self.assertRaises(APIError) as raised,
        ):
            tts_router.synthesize_speech(SpeechRequest(text="zu langer Text"), MagicMock())

        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(raised.exception.code, "TTS_TEXT_TOO_LONG")


if __name__ == "__main__":
    unittest.main()
