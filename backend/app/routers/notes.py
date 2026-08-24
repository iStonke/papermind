import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.notes import (
    NoteCreateRequest,
    NoteListResponse,
    NoteRead,
    NoteSearchScope,
    NoteTextGenerationRequest,
    NoteUpdateRequest,
)
from app.services.note_service import NoteService
from app.services.note_ai import NoteAIService


router = APIRouter(prefix="/api/notes", tags=["Notes"])


@router.post(
    "/ai/generate",
    summary="Generate text for the note editor",
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def generate_note_text(
    payload: NoteTextGenerationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = NoteAIService(db, user.id)
    try:
        plan = service.prepare(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StreamingResponse(
        service.stream(plan),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=NoteListResponse, summary="List notes")
def list_notes(
    in_trash: bool = Query(default=False, description="Show notes in trash"),
    document_id: uuid.UUID | None = Query(default=None, description="Only notes linked to this document"),
    q: str | None = Query(default=None, max_length=256, description="Search note title and body"),
    search_scope: NoteSearchScope = Query(default="all", description="Search title, body, or both"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteListResponse:
    return NoteListResponse(
        items=NoteService(db, user.id).list_notes(
            in_trash=in_trash,
            document_id=document_id,
            q=q,
            search_scope=search_scope,
        )
    )


@router.post(
    "",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
    responses={422: {"model": ErrorResponse}},
)
def create_note(
    payload: NoteCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    return NoteRead.model_validate(NoteService(db, user.id).create_note(payload))


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Get a note",
    responses={404: {"model": ErrorResponse}},
)
def get_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).get_note(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return NoteRead.model_validate(note)


@router.get(
    "/{note_id}/backlinks",
    response_model=NoteListResponse,
    summary="Notes that reference this note",
)
def note_backlinks(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteListResponse:
    return NoteListResponse(items=NoteService(db, user.id).list_references("note", note_id))


@router.post(
    "/{note_id}/trash",
    response_model=NoteRead,
    summary="Move a note to trash",
    responses={404: {"model": ErrorResponse}},
)
def trash_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).trash_note(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return NoteRead.model_validate(note)


@router.post(
    "/{note_id}/restore",
    response_model=NoteRead,
    summary="Restore a note from trash",
    responses={404: {"model": ErrorResponse}},
)
def restore_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).restore_note(note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz im Papierkorb nicht gefunden")
    return NoteRead.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=NoteRead,
    summary="Update a note",
    responses={404: {"model": ErrorResponse}},
)
def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).update_note(note_id, payload)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return NoteRead.model_validate(note)


@router.delete(
    "/trash",
    summary="Permanently delete all notes in trash",
)
def empty_notes_trash(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int | bool]:
    deleted_count = NoteService(db, user.id).empty_trash()
    return {"ok": True, "deleted_count": deleted_count}


@router.delete(
    "/{note_id}",
    response_model=OkResponse,
    summary="Permanently delete a note",
    responses={404: {"model": ErrorResponse}},
)
def delete_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    if not NoteService(db, user.id).delete_note(note_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return OkResponse()
