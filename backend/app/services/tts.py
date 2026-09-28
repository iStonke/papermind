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


def split_speech_text(text: str, max_chars: int = 6000) -> list[str]:
    """Split long prose at paragraph/sentence boundaries for bounded inference."""
    normalized = " ".join(str(text or "").split())
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


def _speech_units(text: str) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n", str(text or "")):
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        units.extend(part.strip() for part in _SENTENCE_BOUNDARY_RE.split(paragraph) if part.strip())
    return units


def segment_speech_text(text: str, *, mode: str = "auto", max_chars: int = 6000) -> list[SpeechSegment]:
    """Split text into bounded German/English segments for Piper synthesis."""
    normalized_mode = mode if mode in {"auto", "de", "en"} else "auto"
    if normalized_mode != "auto":
        return [SpeechSegment(chunk, normalized_mode) for chunk in split_speech_text(text, max_chars)]

    units = _speech_units(text)
    if not units:
        return []
    evidence = [_language_evidence(unit) for unit in units]
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
    for unit, language in zip(units, languages, strict=True):
        for chunk in split_speech_text(unit, max_chars):
            if segments and segments[-1].language == language and len(segments[-1].text) + len(chunk) + 1 <= max_chars:
                previous = segments[-1]
                segments[-1] = SpeechSegment(f"{previous.text} {chunk}", language)
            else:
                segments.append(SpeechSegment(chunk, language))
    return segments


def merge_wav_bytes(parts: list[bytes]) -> bytes:
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
        for frame_data in frames:
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
            # Piper/espeak and the Pi CPU are most predictable with one inference
            # at a time. FastAPI may call this service from multiple worker threads.
            with self._synthesis_lock:
                with wave.open(output, "wb") as wav_file:
                    if model in {"standard", "english"}:
                        piper_voice.synthesize_wav(text, wav_file)
                    else:
                        from piper import SynthesisConfig

                        piper_voice.synthesize_wav(
                            text,
                            wav_file,
                            SynthesisConfig(speaker_id=self.EMOTIONAL_SPEAKERS[voice]),
                        )
        except Exception as exc:  # pragma: no cover - native inference failure
            logger.exception("Piper speech synthesis failed")
            raise TTSUnavailableError("Piper speech synthesis failed") from exc
        return output.getvalue()


tts_service = PiperTTSService()
