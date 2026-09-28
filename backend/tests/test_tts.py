import io
import unittest
import wave
from unittest.mock import MagicMock, patch

from app.core.errors import APIError
from app.routers import tts as tts_router
from app.schemas.tts import SpeechRequest
from app.services.tts import PiperTTSService, TTSUnavailableError, segment_speech_text


class _FakeVoice:
    def __init__(self) -> None:
        self.synthesis_config = None

    def synthesize_wav(self, text, wav_file, synthesis_config=None) -> None:
        self.synthesis_config = synthesis_config
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * max(1, len(text)))


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


class SpeechSegmentationTest(unittest.TestCase):
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


class TTSEndpointTest(unittest.TestCase):
    def test_endpoint_returns_inline_audio(self) -> None:
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part"),
            patch.object(tts_router, "merge_wav_bytes", return_value=b"RIFFtest"),
        ):
            response = tts_router.synthesize_speech(SpeechRequest(text="  Hallo   Welt  "), MagicMock())

        self.assertEqual(response.media_type, "audio/wav")
        self.assertEqual(response.body, b"RIFFtest")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_endpoint_forwards_voice_preset(self) -> None:
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part") as synthesize,
            patch.object(tts_router, "merge_wav_bytes", return_value=b"RIFF"),
        ):
            tts_router.synthesize_speech(
                SpeechRequest(text="Hallo", voice="whisper"),
                MagicMock(),
            )

        synthesize.assert_called_once_with("Hallo", voice="whisper", language="de")

    def test_endpoint_uses_automatic_language_segments(self) -> None:
        text = (
            "Das ist ein deutscher Satz und er wird korrekt erkannt. "
            "This is an English sentence and it is detected correctly."
        )
        with (
            patch.object(tts_router.tts_service, "synthesize_wav", return_value=b"part") as synthesize,
            patch.object(tts_router, "merge_wav_bytes", return_value=b"RIFF"),
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
