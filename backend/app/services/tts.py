from __future__ import annotations

import io
import logging
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("papermind.tts")


class TTSUnavailableError(RuntimeError):
    """Raised when the configured local voice cannot be loaded."""


def _speech_paragraphs(text: str) -> list[str]:
    return [" ".join(line.split()) for line in str(text or "").splitlines() if line.strip()]


def split_speech_text(text: str, max_chars: int = 6000) -> list[str]:
    """Split long prose at paragraph/sentence boundaries for bounded inference."""
    normalized = "\n".join(_speech_paragraphs(text))
    if not normalized:
        return []
    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        candidates = [match.end() for match in re.finditer(r"[.!?;:]\s+", window)]
        split_at = candidates[-1] if candidates else window.rfind(" ")
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


@dataclass(frozen=True)
class SpeechSegment:
    text: str
    language: str


_GERMAN_WORDS = frozenset(
    "aber als auch auf aus bei bin bis das dass dem den der des die doch durch ein eine einer eines "
    "für gegen hat haben ich im in ist kann kein man mit nicht noch oder schon sich sie sind so über "
    "um und vom von vor war was weil wenn werden wie wir wird wo zu zum zur".split()
)
_ENGLISH_WORDS = frozenset(
    "a about after all also an and are as at be because been before but by can could did do does for "
    "from had has have he her here his how i if in into is it its may more my no not of on one or our "
    "should so than that the their them then there these they this to up was we were what when which "
    "who will with would you your".split()
)
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-z]+)?")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])(?:[\"'»”)]*)\s+")
_GERMAN_ABBREVIATIONS = (
    (r"\bz\.\s*B\.", "zum Beispiel"),
    (r"\bd\.\s*h\.", "das heißt"),
    (r"\bu\.\s*a\.", "unter anderem"),
    (r"\bu\.\s*U\.", "unter Umständen"),
    (r"\bbzw\.", "beziehungsweise"),
    (r"\bggf\.", "gegebenenfalls"),
    (r"\bca\.", "circa"),
    (r"\binkl\.", "inklusive"),
    (r"\busw\.", "und so weiter"),
)


def _spoken_abbreviation(match: re.Match[str], replacement: str) -> str:
    spoken = replacement[0].upper() + replacement[1:] if match.group()[0].isupper() else replacement
    following = match.string[match.end():]
    # A sentence-final abbreviation also supplies the sentence's full stop.
    if not following.strip() or (match.group().lower() == "usw." and re.match(r"\s+[A-ZÄÖÜ]", following)):
        spoken += "."
    return spoken


def prepare_speech_text(text: str, *, language: str = "de") -> str:
    """Expand spoken abbreviations without changing the stored note."""
    paragraphs = _speech_paragraphs(text)
    if language == "de":
        for pattern, replacement in _GERMAN_ABBREVIATIONS:
            paragraphs = [re.sub(
                pattern + r"(?=\s|$|[,;:!?])",
                lambda match: _spoken_abbreviation(match, replacement),
                line,
                flags=re.IGNORECASE,
            ) for line in paragraphs]
    return "\n".join(paragraphs)


def _language_evidence(text: str) -> tuple[str | None, int]:
    words = [word.lower().replace("’", "'") for word in _WORD_RE.findall(text)]
    if not words:
        return None, 0
    german = sum(1 for word in words if word in _GERMAN_WORDS)
    english = sum(1 for word in words if word in _ENGLISH_WORDS)
    german += sum(2 for word in words if re.search(r"[äöüß]", word))
    english += sum(1 for word in words if "'" in word or word.endswith("ing"))
    difference = abs(german - english)
    # Names, headings and isolated loanwords intentionally inherit their
    # surrounding language instead of causing a one-word voice change.
    if len(words) < 4 or difference < 2:
        return None, difference
    if german > english:
        return "de", difference
    if english > german:
        return "en", difference
    return None, 0


def _speech_units(text: str) -> list[tuple[str, int]]:
    units: list[tuple[str, int]] = []
    for index, paragraph in enumerate(_speech_paragraphs(text)):
        units.extend((part.strip(), index) for part in _SENTENCE_BOUNDARY_RE.split(paragraph) if part.strip())
    return units


def segment_speech_text(text: str, *, mode: str = "auto", max_chars: int = 6000) -> list[SpeechSegment]:
    """Split text into bounded German/English segments for Piper synthesis."""
    normalized_mode = mode if mode in {"auto", "de", "en"} else "auto"
    if normalized_mode != "auto":
        return [SpeechSegment(chunk, normalized_mode) for chunk in split_speech_text(text, max_chars)]

    units = _speech_units(text)
    if not units:
        return []
    evidence = [_language_evidence(unit) for unit, _paragraph in units]
    german_weight = sum(weight for (language, weight) in evidence if language == "de")
    english_weight = sum(weight for (language, weight) in evidence if language == "en")
    fallback = "en" if english_weight > german_weight else "de"
    languages: list[str] = []
    for index, (language, _weight) in enumerate(evidence):
        if language is not None:
            languages.append(language)
            continue
        previous = languages[-1] if languages else None
        following = next((item[0] for item in evidence[index + 1:] if item[0] is not None), None)
        languages.append(previous or following or fallback)

    segments: list[SpeechSegment] = []
    previous_paragraph = None
    for (unit, paragraph), language in zip(units, languages, strict=True):
        for chunk in split_speech_text(unit, max_chars):
            separator = " " if paragraph == previous_paragraph else "\n"
            if segments and segments[-1].language == language and len(segments[-1].text) + len(chunk) + 1 <= max_chars:
                previous = segments[-1]
                segments[-1] = SpeechSegment(f"{previous.text}{separator}{chunk}", language)
            else:
                segments.append(SpeechSegment(chunk, language))
            previous_paragraph = paragraph
    return segments


def merge_wav_bytes(parts: list[bytes], *, pause_seconds: float = 0.0) -> bytes:
    if not parts:
        raise ValueError("No audio parts to merge")
    output = io.BytesIO()
    reference: tuple[int, int, int, str, str] | None = None
    frames: list[bytes] = []
    for part in parts:
        with wave.open(io.BytesIO(part), "rb") as source:
            params = (
                source.getnchannels(), source.getsampwidth(), source.getframerate(),
                source.getcomptype(), source.getcompname(),
            )
            if reference is None:
                reference = params
            elif params != reference:
                raise ValueError("Audio parts use incompatible WAV formats")
            frames.append(source.readframes(source.getnframes()))
    assert reference is not None
    with wave.open(output, "wb") as target:
        target.setnchannels(reference[0])
        target.setsampwidth(reference[1])
        target.setframerate(reference[2])
        target.setcomptype(reference[3], reference[4])
        for index, frame_data in enumerate(frames):
            if index and pause_seconds > 0:
                target.writeframes(bytes(round(reference[2] * pause_seconds) * reference[0] * reference[1]))
            target.writeframes(frame_data)
    return output.getvalue()


class PiperTTSService:
    """Lazy, process-local Piper voices with serialized CPU inference."""

    EMOTIONAL_SPEAKERS = {
        "neutral": 4,
        "amused": 0,
        "sleepy": 5,
        "whisper": 7,
    }

    SENTENCE_PAUSE_SECONDS = 0.18
    PARAGRAPH_PAUSE_SECONDS = 0.38

    @staticmethod
    def _trim_edge_silence(samples: Any, sample_rate: int) -> Any:
        """Bound model-generated edge silence; retain 40 ms around speech."""
        import numpy as np

        if samples.size == 0:
            return samples
        peak = float(np.max(np.abs(samples)))
        if peak < 1e-8:
            return samples[:0]
        window = max(1, round(sample_rate * 0.01))
        padding = (-samples.size) % window
        frames = np.pad(samples, (0, padding)).reshape(-1, window)
        energy = np.sqrt(np.mean(frames * frames, axis=1))
        voiced = np.flatnonzero(energy > peak * 0.002)
        if voiced.size == 0:
            return samples
        guard = round(sample_rate * 0.04)
        start = max(0, int(voiced[0]) * window - guard)
        end = min(samples.size, (int(voiced[-1]) + 1) * window + guard)
        return samples[start:end]

    def __init__(
        self,
        model_path: str | Path | None = None,
        emotional_model_path: str | Path | None = None,
        english_model_path: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.model_paths = {
            "standard": Path(model_path or settings.tts_model_path),
            "emotional": Path(emotional_model_path or settings.tts_emotional_model_path),
            "english": Path(english_model_path or settings.tts_english_model_path),
        }
        self._voices: dict[str, Any] = {}
        self._load_lock = threading.Lock()
        self._synthesis_lock = threading.Lock()

    def _get_voice(self, model: str) -> Any:
        if model in self._voices:
            return self._voices[model]

        with self._load_lock:
            if model in self._voices:
                return self._voices[model]
            model_path = self.model_paths[model]
            if not model_path.is_file():
                raise TTSUnavailableError(f"Piper voice model not found: {model_path}")
            try:
                from piper import PiperVoice

                self._voices[model] = PiperVoice.load(str(model_path))
            except Exception as exc:  # pragma: no cover - depends on native runtime/model
                logger.exception("Unable to load Piper voice model")
                raise TTSUnavailableError("Piper voice model could not be loaded") from exc
        return self._voices[model]

    def synthesize_wav(self, text: str, *, voice: str = "standard", language: str = "de") -> bytes:
        model = "english" if language == "en" else ("standard" if voice == "standard" else "emotional")
        piper_voice = self._get_voice(model)
        output = io.BytesIO()
        try:
            import numpy as np
            from piper import SynthesisConfig

            # Keep the voice's trained speed/intonation. Normalize the complete
            # passage once, so quiet sentences are not amplified independently.
            config = SynthesisConfig(
                speaker_id=self.EMOTIONAL_SPEAKERS[voice] if model == "emotional" else None,
                normalize_audio=False,
            )
            # Piper/espeak and the Pi CPU are most predictable with one inference
            # at a time. FastAPI may call this service from multiple worker threads.
            with self._synthesis_lock:
                audio_parts = []
                sample_rate = None
                last_paragraph = None
                for index, paragraph in enumerate(_speech_paragraphs(prepare_speech_text(text, language=language))):
                    for chunk in piper_voice.synthesize(paragraph, syn_config=config):
                        if chunk.sample_width != 2 or chunk.sample_channels != 1:
                            raise ValueError("Unexpected Piper audio format")
                        if sample_rate is not None and sample_rate != chunk.sample_rate:
                            raise ValueError("Incompatible Piper sample rates")
                        sample_rate = chunk.sample_rate
                        samples = self._trim_edge_silence(chunk.audio_float_array, sample_rate)
                        if samples.size == 0:
                            continue
                        if audio_parts:
                            pause = self.SENTENCE_PAUSE_SECONDS if last_paragraph == index else self.PARAGRAPH_PAUSE_SECONDS
                            audio_parts.append(np.zeros(round(sample_rate * pause), dtype=np.float32))
                        audio_parts.append(samples)
                        last_paragraph = index
                if not audio_parts or sample_rate is None:
                    raise ValueError("Piper produced no speech audio")
                samples = np.concatenate(audio_parts)
                if not np.all(np.isfinite(samples)):
                    raise ValueError("Piper produced invalid audio samples")
                peak = float(np.max(np.abs(samples)))
                if peak > 1e-8:
                    samples = samples * (0.9 / peak)
                frames = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
                with wave.open(output, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(frames)
        except Exception as exc:  # pragma: no cover - native inference failure
            logger.exception("Piper speech synthesis failed")
            raise TTSUnavailableError("Piper speech synthesis failed") from exc
        return output.getvalue()


tts_service = PiperTTSService()
