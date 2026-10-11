import io
import time
import wave

from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import APIError
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.tts import SpeechRequest
from app.services.tts import TTSUnavailableError, merge_speech_audio, segment_speech_text
from app.services.speech_engines import speech_service as tts_service

router = APIRouter(prefix="/api/tts", tags=["Text to Speech"])


@router.get("/engines", summary="Availability of local speech engines")
def speech_engines(_user: User = Depends(get_current_user)) -> dict:
    return {"items": tts_service.engines()}


@router.post(
    "/speech",
    response_class=Response,
    summary="Synthesize selected note text with a local speech engine",
    responses={
        413: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def synthesize_speech(
    payload: SpeechRequest,
    _user: User = Depends(get_current_user),
) -> Response:
    settings = get_settings()
    if len(payload.text) > settings.tts_max_chars:
        raise APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "TTS_TEXT_TOO_LONG",
            f"Bitte höchstens {settings.tts_max_chars} Zeichen zum Vorlesen markieren.",
        )
    started = time.perf_counter()
    try:
        segments = segment_speech_text(
            payload.text,
            mode=payload.language_mode,
            max_chars=settings.tts_max_chars,
        )
        audio = merge_speech_audio([
            tts_service.synthesize_wav(segment.text, voice=payload.voice, language=segment.language, options=payload.options)
            for segment in segments
        ], segments, options=payload.options)
    except TTSUnavailableError as exc:
        raise APIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TTS_UNAVAILABLE",
            "Die lokale Sprachausgabe ist derzeit nicht verfügbar. Bitte prüfe die gewählte Engine unter Einstellungen → Notizen → Sprachausgabe.",
        ) from exc

    with wave.open(io.BytesIO(audio), "rb") as wav:
        duration = wav.getnframes() / wav.getframerate()
    generation_ms = (time.perf_counter() - started) * 1000
    used = sorted({"piper" if segment.language == "en" else payload.options.engine for segment in segments})
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "Server-Timing": f"tts;dur={generation_ms:.1f}",
            "X-Speech-Duration": f"{duration:.3f}",
            "X-Speech-Generation-Ms": f"{generation_ms:.1f}",
            "X-Speech-Engine": ",".join(used),
            "Content-Disposition": 'inline; filename="papermind-vorlesen.wav"',
        },
    )
