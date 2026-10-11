"""Local Piper and Thorsten HTTP engines; no browser-provided target URLs."""

import io
import struct
import threading
import wave
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.core.config import get_settings
from app.schemas.speech_options import SpeechOptions
from app.services.tts import PiperTTSService, TTSUnavailableError, _speech_units, prepare_speech_text, split_speech_text, tts_service


def decode_engine_wav(data: bytes):
    """Decode PCM/float WAVs emitted by the two local engines into mono floats."""
    import numpy as np

    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("The engine did not return a WAV file")
    fmt = frames = None
    offset = 12
    while offset + 8 <= len(data):
        kind, length = struct.unpack_from("<4sI", data, offset)
        start, end = offset + 8, offset + 8 + length
        if end > len(data):
            raise ValueError("Incomplete WAV file")
        if kind == b"fmt ":
            fmt = data[start:end]
        elif kind == b"data":
            frames = data[start:end]
        offset = end + length % 2
    if fmt is None or frames is None or len(fmt) < 16:
        raise ValueError("Missing WAV format or audio")
    encoding, channels, rate, _byte_rate, block, bits = struct.unpack_from("<HHIIHH", fmt)
    if channels not in (1, 2) or bits not in (16, 32) or not 8000 <= rate <= 96000 or block != channels * bits // 8:
        raise ValueError("Unsupported WAV format")
    if not frames or len(frames) % block:
        raise ValueError("Invalid WAV frame data")
    if encoding == 1 and bits == 16:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif encoding == 1 and bits == 32:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    elif encoding == 3 and bits == 32:
        samples = np.frombuffer(frames, dtype="<f4").copy()
    else:
        raise ValueError("Unsupported WAV encoding")
    if not np.all(np.isfinite(samples)):
        raise ValueError("Invalid WAV samples")
    if channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    return samples, rate


class SpeechEngineService:
    SENTENCE_PAUSE_SECONDS = PiperTTSService.SENTENCE_PAUSE_SECONDS
    PARAGRAPH_PAUSE_SECONDS = PiperTTSService.PARAGRAPH_PAUSE_SECONDS
    MAX_RESPONSE_BYTES = 32 * 1024 * 1024

    def __init__(self):
        self._locks = {engine: threading.Lock() for engine in ("kokoro", "cosyvoice")}

    @staticmethod
    def endpoint(engine: str) -> str:
        settings = get_settings()
        return str(settings.tts_kokoro_url if engine == "kokoro" else settings.tts_cosyvoice_url).rstrip("/")

    def engines(self) -> list[dict]:
        def inspect(engine):
            url = self.endpoint(engine)
            result = {"id": engine, "name": "Thorsten Kokoro" if engine == "kokoro" else "Thorsten CosyVoice",
                      "available": False, "languages": ["de"], "english_fallback": "piper"}
            if not url:
                return {**result, "status": "not_configured"}
            try:
                with httpx.Client(timeout=1.5, trust_env=False) as client:
                    response = client.get(url + "/health")
                    response.raise_for_status()
                    health = response.json()
                    result["available"] = isinstance(health, dict) and health.get("status") in ("ok", "healthy", "ready")
            except (httpx.HTTPError, ValueError):
                pass
            return {**result, "status": "ready" if result["available"] else "not_running"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            optional = list(pool.map(inspect, ("kokoro", "cosyvoice")))
        paths = tts_service.model_paths
        available = paths["standard"].is_file() and paths["english"].is_file()
        return [{"id": "piper", "name": "Piper", "available": available, "status": "ready" if available else "missing_model", "languages": ["de", "en"]}, *optional]

    def _request_audio(self, engine: str, text: str, speed: float) -> bytes:
        endpoint = self.endpoint(engine)
        if not endpoint:
            raise TTSUnavailableError(f"{engine} ist noch nicht eingerichtet.")
        body = {"text": text, "speed": speed}
        kwargs = {"json": body} if engine == "kokoro" else {"data": body}
        try:
            with httpx.Client(timeout=get_settings().tts_external_timeout_seconds, trust_env=False) as client:
                with client.stream("POST", endpoint + "/tts", **kwargs) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.MAX_RESPONSE_BYTES:
                            raise ValueError("Audio response exceeds limit")
                        chunks.append(chunk)
                    return b"".join(chunks)
        except (httpx.HTTPError, ValueError) as exc:
            raise TTSUnavailableError(f"Die lokale Engine {engine} ist nicht erreichbar oder liefert keine gültige Audiodatei.") from exc

    def synthesize_wav(self, text: str, *, voice="standard", language="de", options: SpeechOptions | None = None) -> bytes:
        options = options or SpeechOptions()
        if options.engine == "piper" or language == "en":
            return tts_service.synthesize_wav(text, voice=voice, language=language, options=options)
        import numpy as np

        parts, last_paragraph = [], None
        target_rate = 22050  # Piper English and both German HTTP engines can be combined.
        try:
            prepared = prepare_speech_text(text, language=language, options=options)
            with self._locks[options.engine]:
                for sentence, paragraph in _speech_units(prepared):
                    for chunk in split_speech_text(sentence, max_chars=900):
                        samples, rate = decode_engine_wav(self._request_audio(options.engine, chunk, options.speed))
                        samples = PiperTTSService._trim_edge_silence(samples, rate)
                        if samples.size == 0:
                            continue
                        if rate != target_rate:
                            positions = np.arange(max(1, round(samples.size * target_rate / rate))) * rate / target_rate
                            samples = np.interp(positions, np.arange(samples.size), samples).astype(np.float32)
                        if parts:
                            pause = options.sentence_pause if last_paragraph == paragraph else options.paragraph_pause
                            parts.append(np.zeros(round(target_rate * pause), dtype=np.float32))
                        parts.append(samples)
                        last_paragraph = paragraph
            if not parts:
                raise ValueError("Engine produced no speech")
            samples = np.concatenate(parts)
            peak = float(np.max(np.abs(samples)))
            if peak > 1e-8:
                samples = samples * (0.9 / peak)
            output = io.BytesIO()
            with wave.open(output, "wb") as target:
                target.setparams((1, 2, target_rate, 0, "NONE", "not compressed"))
                target.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
            return output.getvalue()
        except (ValueError, KeyError) as exc:
            raise TTSUnavailableError("Die lokale Engine hat keine abspielbare Sprachausgabe erzeugt.") from exc


speech_service = SpeechEngineService()
