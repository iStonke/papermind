from __future__ import annotations

import io
import logging
import threading
import wave
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("papermind.tts")


class TTSUnavailableError(RuntimeError):
    """Raised when the configured local voice cannot be loaded."""


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
