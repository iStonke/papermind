from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import APIError
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.tts import SpeechRequest
from app.services.tts import TTSUnavailableError, tts_service

router = APIRouter(prefix="/api/tts", tags=["Text to Speech"])


@router.post(
    "/speech",
    response_class=Response,
    summary="Synthesize selected note text locally with Piper",
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
    try:
        audio = tts_service.synthesize_wav(payload.text, voice=payload.voice)
    except TTSUnavailableError as exc:
        raise APIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "TTS_UNAVAILABLE",
            "Die lokale Sprachausgabe ist derzeit nicht verfügbar.",
        ) from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="papermind-vorlesen.wav"',
        },
    )
