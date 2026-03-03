from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ai import AIAskRequest, AIAskResponse
from app.schemas.common import ErrorResponse
from app.services.ai import AIService

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post(
    "/ask",
    response_model=AIAskResponse,
    summary="Ask a question and get grounded answer with citations",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def ask_question(payload: AIAskRequest, db: Session = Depends(get_db)) -> AIAskResponse:
    service = AIService(db)
    return AIAskResponse.model_validate(service.ask(payload))
