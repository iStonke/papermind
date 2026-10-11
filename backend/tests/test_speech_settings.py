import io
import struct
import tempfile
import unittest
import uuid
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import numpy as np
from pydantic import ValidationError

from app.schemas.speech_options import SpeechOptions, SpeechPronunciation
from app.schemas.jobs import NoteAudioExportCreateRequest
from app.schemas.settings import UISettingsRead, UISettingsPatch
from app.services.speech_text import apply_pronunciations, normalize_german_numbers
from app.services.speech_engines import SpeechEngineService, decode_engine_wav
from app.services.tts import PiperTTSService, SpeechSegment, TTSUnavailableError, merge_speech_audio, prepare_speech_text
from app.services.note_audio_jobs import NoteAudioJobStore


def wav_audio(rate=24000, frames=2400):
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(np.full(frames, 3000, dtype='<i2').tobytes())
    return output.getvalue()


class GermanSpeechTextTests(unittest.TestCase):
    def test_dates_times_and_units_with_sentence_punctuation(self):
        self.assertEqual(
            normalize_german_numbers('Am 11.10.2026 um 14:30 Uhr: 12,5 % und 3 kg.'),
            'Am elften Oktober zweitausendsechsundzwanzig um vierzehn Uhr dreißig: zwölf Komma fünf Prozent und drei Kilogramm.',
        )
        self.assertEqual(normalize_german_numbers('11.10.2026. 1 h und 1 min.'), 'elfter Oktober zweitausendsechsundzwanzig. eine Stunde und eine Minute.')
        self.assertEqual(normalize_german_numbers('Nummer 3. 1.234,50 €.'), 'Nummer drei. eintausendzweihundertvierunddreißig Euro und fünfzig Cent.')
        self.assertEqual(normalize_german_numbers('Um 01:00 Uhr, minus -2 °C.'), 'Um ein Uhr, minus minus zwei Grad Celsius.')

    def test_ordinals_preserve_fluent_german_phrases(self):
        self.assertEqual(normalize_german_numbers('Im 2. Semester, das 3. Kapitel und die 1. Aufgabe.'),
                         'Im zweiten Semester, das dritte Kapitel und die erste Aufgabe.')
        self.assertEqual(normalize_german_numbers('Am 11. Oktober. Nummer 3.'), 'Am elften Oktober. Nummer drei.')

    def test_invalid_dates_and_identifiers_are_preserved(self):
        text = '31.02.2026 25:70 v2.4 A123 00123 12345678 1.2.3 https://example.org/v2?x=12 a12@example.org'
        self.assertEqual(normalize_german_numbers(text), text)

    def test_many_units_do_not_exhaust_placeholder_range(self):
        text = '1% ' * 6500
        self.assertEqual(normalize_german_numbers(text), 'ein Prozent ' * 6500)

    def test_dictionary_is_literal_longest_first_one_pass(self):
        entries = [
            SpeechPronunciation(word='EA', pronunciation='Einsendeaufgabe'),
            SpeechPronunciation(word='EA Kurs', pronunciation='Kursaufgabe'),
            SpeechPronunciation(word='Einsendeaufgabe', pronunciation='NICHT REKURSIV'),
            SpeechPronunciation(word='C++', pronunciation='C plus plus'),
            SpeechPronunciation(word='QIS', pronunciation='Kiss', enabled=False),
        ]
        self.assertEqual(apply_pronunciations('ea Kurs, EA, REAKTOR, C++ und QIS.', entries), 'Kursaufgabe, Einsendeaufgabe, REAKTOR, C plus plus und QIS.')

    def test_dictionary_case_sensitive_and_numbers_switch(self):
        options = SpeechOptions(normalize_numbers=False, pronunciations=[SpeechPronunciation(word='Pi', pronunciation='Pai', case_sensitive=True)])
        self.assertEqual(prepare_speech_text('Pi pi mit 3 kg', options=options), 'Pai pi mit 3 kg')
        self.assertEqual(prepare_speech_text('14:30 Uhr und 3 kg', language='en', options=SpeechOptions()), '14:30 Uhr und 3 kg')


class SpeechOptionsTests(unittest.TestCase):
    def test_legacy_preferences_and_exports_get_defaults(self):
        self.assertEqual(UISettingsRead().notes_tts_options, SpeechOptions())
        self.assertEqual(NoteAudioExportCreateRequest(text='Text').options, SpeechOptions())
        self.assertEqual(UISettingsPatch(notes_tts_options={'speed': 1.1}).notes_tts_options.speed, 1.1)

    def test_invalid_speed_pause_engine_and_dictionary_are_rejected(self):
        for options in [
            {'speed': float('nan')}, {'speed': 0}, {'speed': 2},
            {'sentence_pause': 0.5, 'paragraph_pause': 0.1},
            {'engine': 'remote'}, {'url': 'http://unknown/'},
            {'pronunciations': [{'word': 'a\nb', 'pronunciation': 'abc'}]},
            {'pronunciations': [{'word': 'QIS', 'pronunciation': 'Kiss'}, {'word': 'qis', 'pronunciation': 'Kis'}]},
        ]:
            with self.subTest(options=options), self.assertRaises(ValidationError):
                SpeechOptions.model_validate(options)

    def test_export_job_snapshots_options_and_retry_retains_them(self):
        options = SpeechOptions(engine='kokoro', speed=1.15, pronunciations=[SpeechPronunciation(word='QIS', pronunciation='Kiss')])
        with tempfile.TemporaryDirectory() as directory:
            store = NoteAudioJobStore(Path(directory))
            owner = uuid.uuid4()
            job = store.create(owner_id=owner, note_id=uuid.uuid4(), note_title='Probe', text='Text', voice='neutral', speech_options=options.model_dump())
            store.cancel(job['id'], owner)
            store.restart(job['id'], owner)
            reopened = NoteAudioJobStore(Path(directory))
            self.assertEqual(reopened.get(job['id'])['speech_options'], options.model_dump())

    def test_piper_uses_inverse_speed_and_chosen_pauses(self):
        configs = []
        class FakeVoice:
            def synthesize(self, text, *, syn_config):
                configs.append(syn_config)
                yield SimpleNamespace(sample_rate=22050, sample_width=2, sample_channels=1, audio_float_array=np.full(2205, .2, dtype=np.float32))
        service = PiperTTSService('/unused')
        options = SpeechOptions(speed=1.25, sentence_pause=.25, paragraph_pause=.5)
        with patch.object(service, '_get_voice', return_value=FakeVoice()):
            audio = service.synthesize_wav('Erster Satz.\nZweiter Absatz.', options=options)
        with wave.open(io.BytesIO(audio)) as wav:
            self.assertEqual(wav.getnframes(), 4410 + 11025)
        self.assertAlmostEqual(configs[0].length_scale, .8)

    def test_option_pauses_survive_language_boundary(self):
        segments = [SpeechSegment(text='Deutsch.', language='de'), SpeechSegment(text='English.', language='en', paragraph_break=True)]
        result = merge_speech_audio([wav_audio(22050, 2205)] * 2, segments, options=SpeechOptions(paragraph_pause=.7))
        with wave.open(io.BytesIO(result)) as wav:
            self.assertEqual(wav.getnframes(), 4410 + round(.7 * 22050))


class OptionalSpeechEnginesTests(unittest.TestCase):
    def test_kokoro_json_and_cosyvoice_form_contract(self):
        seen = []
        def handle(request):
            seen.append(request)
            return httpx.Response(200, content=wav_audio())
        real_client = httpx.Client
        def client(**kwargs):
            return real_client(transport=httpx.MockTransport(handle), **kwargs)
        service = SpeechEngineService()
        for engine in ['kokoro', 'cosyvoice']:
            with patch('app.services.speech_engines.httpx.Client', side_effect=client):
                audio = service.synthesize_wav('Ein Satz.', options=SpeechOptions(engine=engine, speed=1.2))
            with wave.open(io.BytesIO(audio)) as wav:
                self.assertEqual(wav.getframerate(), 22050)
                self.assertEqual(wav.getnframes(), 2205)
        self.assertIn(b'"speed":1.2', seen[0].content)
        self.assertIn('application/json', seen[0].headers['content-type'])
        self.assertEqual(seen[1].content, b'text=Ein+Satz.&speed=1.2')
        self.assertIn('application/x-www-form-urlencoded', seen[1].headers['content-type'])

    def test_english_falls_back_with_same_options(self):
        options = SpeechOptions(engine='kokoro', speed=.9)
        with patch('app.services.speech_engines.tts_service.synthesize_wav', return_value=b'audio') as synth:
            self.assertEqual(SpeechEngineService().synthesize_wav('English text.', language='en', options=options), b'audio')
        synth.assert_called_once_with('English text.', voice='standard', language='en', options=options)

    def test_bad_engine_audio_is_a_clear_unavailable_error(self):
        with patch.object(SpeechEngineService, '_request_audio', return_value=b'not audio'):
            with self.assertRaises(TTSUnavailableError):
                SpeechEngineService().synthesize_wav('Deutsch.', options=SpeechOptions(engine='kokoro'))

    def test_float_stereo_wav_and_nonfinite_samples(self):
        samples = np.array([.2, .4, -.2, -.4], dtype='<f4')
        fmt = struct.pack('<HHIIHH', 3, 2, 24000, 24000 * 8, 8, 32)
        chunks = b'fmt ' + struct.pack('<I', 16) + fmt + b'data' + struct.pack('<I', samples.nbytes) + samples.tobytes()
        audio = b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks
        mono, rate = decode_engine_wav(audio)
        np.testing.assert_allclose(mono, [.3, -.3])
        self.assertEqual(rate, 24000)
        with self.assertRaises(ValueError):
            decode_engine_wav(audio[:-4] + struct.pack('<f', float('nan')))
