from __future__ import annotations

import io
import logging
import re
import threading
import wave
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
    ) -> None:
        settings = get_settings()
        self.model_paths = {
            "standard": Path(model_path or settings.tts_model_path),
            "emotional": Path(emotional_model_path or settings.tts_emotional_model_path),
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

    def synthesize_wav(self, text: str, *, voice: str = "standard") -> bytes:
        model = "standard" if voice == "standard" else "emotional"
        piper_voice = self._get_voice(model)
        output = io.BytesIO()
        try:
            # Piper/espeak and the Pi CPU are most predictable with one inference
            # at a time. FastAPI may call this service from multiple worker threads.
            with self._synthesis_lock:
                with wave.open(output, "wb") as wav_file:
                    if model == "standard":
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
