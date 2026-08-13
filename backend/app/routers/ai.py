import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.ai import AIAskRequest, AIAskResponse, AIChatSessionRead, AIChatSessionSummary
from app.schemas.common import ErrorResponse
from app.services.ai import AIService
from app.services.chat_sessions import ChatSessionService

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post(
    "/ask",
    response_model=AIAskResponse,
    summary="Ask a question and get grounded answer with citations",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def ask_question(payload: AIAskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AIAskResponse:
    service = AIService(db, user.id)
    return AIAskResponse.model_validate(service.ask(payload))


@router.get("/sessions", response_model=list[AIChatSessionSummary], summary="List saved knowledge conversations")
def list_chat_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AIChatSessionSummary]:
    sessions = ChatSessionService(db, user.id).list_sessions(limit=limit)
    return [AIChatSessionSummary.model_validate(session) for session in sessions]


@router.get("/sessions/latest", response_model=AIChatSessionRead | None, summary="Load the latest active knowledge conversation")
def get_latest_chat_session(
    message_limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIChatSessionRead | None:
    session = ChatSessionService(db, user.id).get_latest_session_history(message_limit=message_limit)
    return AIChatSessionRead.model_validate(session) if session is not None else None


@router.get(
    "/sessions/{session_id}",
    response_model=AIChatSessionRead,
    summary="Load one saved knowledge conversation",
    responses={404: {"model": ErrorResponse}},
)
def get_chat_session(
    session_id: uuid.UUID,
    message_limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIChatSessionRead:
    session = ChatSessionService(db, user.id).get_session_history(session_id, message_limit=message_limit)
    return AIChatSessionRead.model_validate(session)


@router.post(
    "/sessions/{session_id}/archive",
    response_model=AIChatSessionSummary,
    summary="Archive a knowledge conversation without deleting its history",
    responses={404: {"model": ErrorResponse}},
)
def archive_chat_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AIChatSessionSummary:
    session = ChatSessionService(db, user.id).archive_session(session_id)
    return AIChatSessionSummary.model_validate(session)
