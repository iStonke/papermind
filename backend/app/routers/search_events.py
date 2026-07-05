from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.search_events import SearchEventService

router = APIRouter(prefix="/api/search-events", tags=["Search"])


class SearchEventCreate(BaseModel):
    term: str = Field(..., max_length=200)


@router.post(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log a committed search term (owner-scoped)",
)
def create_search_event(
    payload: SearchEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    SearchEventService(db, user.id).record(payload.term)
