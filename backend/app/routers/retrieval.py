from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.retrieval import RetrievalQueryRequest, RetrievalQueryResponse
from app.services.embeddings import EmbeddingService

router = APIRouter(prefix="/api/retrieval", tags=["Retrieval"])


@router.post(
    "/query",
    response_model=RetrievalQueryResponse,
    summary="Retrieve top-k relevant chunks for a query",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def retrieval_query(payload: RetrievalQueryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RetrievalQueryResponse:
    service = EmbeddingService(db, user.id)
    data = service.retrieve(
        query=payload.query,
        top_k=payload.top_k,
        doc_id=payload.filters.doc_id,
        tag_ids=payload.filters.tag_ids,
        date_from=payload.filters.date_from,
        date_to=payload.filters.date_to,
    )
    return RetrievalQueryResponse.model_validate(data)
