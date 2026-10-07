import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.note_learn_highlights import (
    NoteLearnHighlightCreate,
    NoteLearnHighlightListResponse,
    NoteLearnHighlightRead,
    NoteLearnHighlightUpdate,
)
from app.services.note_learn_highlight_service import NoteLearnHighlightService

router = APIRouter(tags=["Note learn highlights"])


@router.get(
    "/api/notes/{note_id}/learn-highlights",
    response_model=NoteLearnHighlightListResponse,
    summary="List learn highlights of a note",
    responses={404: {"model": ErrorResponse}},
)
def list_note_learn_highlights(
    note_id: uuid.UUID,
    document_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteLearnHighlightListResponse:
    items = NoteLearnHighlightService(db, user.id).list_for_note(note_id, document_id)
    return NoteLearnHighlightListResponse(items=[NoteLearnHighlightRead.model_validate(h) for h in items])


@router.post(
    "/api/notes/{note_id}/learn-highlights",
    response_model=NoteLearnHighlightRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a learn highlight for a note",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_note_learn_highlight(
    note_id: uuid.UUID,
    payload: NoteLearnHighlightCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteLearnHighlightRead:
    highlight = NoteLearnHighlightService(db, user.id).create(note_id, payload)
    return NoteLearnHighlightRead.model_validate(highlight)


@router.patch(
    "/api/note-learn-highlights/{highlight_id}",
    response_model=NoteLearnHighlightRead,
    summary="Change the meaning (color) of a learn highlight",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_note_learn_highlight(
    highlight_id: uuid.UUID,
    payload: NoteLearnHighlightUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteLearnHighlightRead:
    highlight = NoteLearnHighlightService(db, user.id).update(highlight_id, payload)
    return NoteLearnHighlightRead.model_validate(highlight)


@router.delete(
    "/api/note-learn-highlights/{highlight_id}",
    response_model=OkResponse,
    summary="Delete a learn highlight",
    responses={404: {"model": ErrorResponse}},
)
def delete_note_learn_highlight(
    highlight_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    NoteLearnHighlightService(db, user.id).delete(highlight_id)
    return OkResponse()


@router.get(
    "/api/documents/{document_id}/learn-highlights",
    response_model=NoteLearnHighlightListResponse,
    summary="All learn highlights of all notes linked to a document",
    responses={404: {"model": ErrorResponse}},
)
def list_document_learn_highlights(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteLearnHighlightListResponse:
    items = NoteLearnHighlightService(db, user.id).list_for_document(document_id)
    return NoteLearnHighlightListResponse(items=[NoteLearnHighlightRead.model_validate(h) for h in items])
