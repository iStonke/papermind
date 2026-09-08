import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.notes import (
    CollectionCreateRequest,
    CollectionListResponse,
    CollectionMoveRequest,
    CollectionRead,
    CollectionReorderRequest,
    CollectionUpdateRequest,
    NoteBlockTemplateCreateRequest,
    NoteBlockTemplateListResponse,
    NoteBlockTemplateRead,
    NoteBlockTemplateUpdateRequest,
    NotebookCreateRequest,
    NotebookListResponse,
    NotebookMoveRequest,
    NotebookReorderRequest,
    NotebookRead,
    NotebookUpdateRequest,
    NoteBulkRequest,
    NoteBulkResult,
    NoteCreateRequest,
    NoteImageRead,
    NoteListResponse,
    NoteRead,
    NoteRevisionCheckpointRequest,
    NoteRevisionListResponse,
    NoteRevisionRead,
    NoteRevisionRestoreRequest,
    NoteSearchScope,
    NoteTagsUpdateRequest,
    NoteTaskToggleRequest,
    NoteTextGenerationRequest,
    NoteUpdateRequest,
    SaveAsTemplateRequest,
)
from app.services.note_service import NoteService
from app.services.note_collection_service import NoteCollectionService
from app.services.note_notebook_service import NoteNotebookService
from app.services.note_block_template_service import NoteBlockTemplateService
from app.services.note_ai import NoteAIService
from app.services.note_images import NoteImageService


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
    dossier_id: uuid.UUID | None = Query(default=None, description="Only notes referencing this dossier"),
    tag_id: uuid.UUID | None = Query(default=None, description="Only notes carrying this tag"),
    collection_id: uuid.UUID | None = Query(
        default=None, description="Only notes in this collection (ignored for templates)"
    ),
    notebook_id: uuid.UUID | None = Query(default=None, description="Only notes in this notebook"),
    no_notebook: bool = Query(default=False, description="Only notes without a notebook"),
    favorites_only: bool = Query(default=False, description="Only favorite notes"),
    templates: bool = Query(default=False, description="List templates instead of regular notes"),
    q: str | None = Query(default=None, max_length=256, description="Search note title and body"),
    search_scope: NoteSearchScope = Query(default="all", description="Search title, body, or both"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteListResponse:
    return NoteListResponse(
        items=NoteService(db, user.id).list_notes(
            in_trash=in_trash,
            document_id=document_id,
            dossier_id=dossier_id,
            tag_id=tag_id,
            collection_id=collection_id,
            notebook_id=notebook_id,
            no_notebook=no_notebook,
            favorites_only=favorites_only,
            templates=templates,
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


@router.post(
    "/bulk",
    response_model=NoteBulkResult,
    summary="Run a bulk action over several notes",
)
def bulk_notes(
    payload: NoteBulkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBulkResult:
    affected = NoteService(db, user.id).bulk_action(payload.action, payload.ids)
    return NoteBulkResult(ok=True, affected=affected)


# --- Sammlungen (oberste Ebene, harte Partition) ----------------------------
# Bewusst VOR den ``/{note_id}``-Routen deklariert (wie Notizbücher).
@router.get("/collections", response_model=CollectionListResponse, summary="List collections")
def list_collections(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionListResponse:
    return CollectionListResponse(items=NoteCollectionService(db, user.id).list_collections())


@router.post(
    "/collections",
    response_model=CollectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a collection",
    responses={409: {"model": ErrorResponse}},
)
def create_collection(
    payload: CollectionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionRead:
    return NoteCollectionService(db, user.id).create_collection(payload)


@router.post(
    "/collections/move",
    response_model=NoteBulkResult,
    summary="Move notes into another collection (detaches their notebook)",
)
def move_notes_to_collection(
    payload: CollectionMoveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBulkResult:
    affected = NoteCollectionService(db, user.id).move_notes(payload.ids, payload.collection_id)
    return NoteBulkResult(ok=True, affected=affected)


@router.post(
    "/collections/reorder",
    response_model=CollectionListResponse,
    summary="Set the display order of collections",
)
def reorder_collections(
    payload: CollectionReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionListResponse:
    return CollectionListResponse(items=NoteCollectionService(db, user.id).reorder_collections(payload.ids))


@router.patch(
    "/collections/{collection_id}",
    response_model=CollectionRead,
    summary="Rename or recolor a collection",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CollectionRead:
    return NoteCollectionService(db, user.id).update_collection(collection_id, payload)


@router.delete(
    "/collections/{collection_id}",
    response_model=OkResponse,
    summary="Delete a collection (non-empty needs reassign_to; last one is protected)",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def delete_collection(
    collection_id: uuid.UUID,
    reassign_to: uuid.UUID | None = Query(
        default=None, description="Target collection for notes/notebooks of a non-empty collection"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    NoteCollectionService(db, user.id).delete_collection(collection_id, reassign_to)
    return OkResponse(ok=True)


# --- Notizbücher (flache Ablageebene) ---------------------------------------
# Bewusst VOR den ``/{note_id}``-Routen deklariert, damit ``/notebooks`` nicht
# als Notiz-ID gedeutet wird.
@router.get("/notebooks", response_model=NotebookListResponse, summary="List notebooks")
def list_notebooks(
    collection_id: uuid.UUID | None = Query(
        default=None, description="Only notebooks in this collection"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotebookListResponse:
    return NotebookListResponse(items=NoteNotebookService(db, user.id).list_notebooks(collection_id))


@router.post(
    "/notebooks",
    response_model=NotebookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notebook",
    responses={409: {"model": ErrorResponse}},
)
def create_notebook(
    payload: NotebookCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotebookRead:
    return NoteNotebookService(db, user.id).create_notebook(payload)


@router.post(
    "/notebooks/move",
    response_model=NoteBulkResult,
    summary="Move notes into a notebook (or out with notebook_id=null)",
)
def move_notes_to_notebook(
    payload: NotebookMoveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBulkResult:
    affected = NoteNotebookService(db, user.id).move_notes(payload.ids, payload.notebook_id)
    return NoteBulkResult(ok=True, affected=affected)


@router.post(
    "/notebooks/reorder",
    response_model=NotebookListResponse,
    summary="Set the display order of notebooks",
)
def reorder_notebooks(
    payload: NotebookReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotebookListResponse:
    return NotebookListResponse(items=NoteNotebookService(db, user.id).reorder_notebooks(payload.ids))


@router.patch(
    "/notebooks/{notebook_id}",
    response_model=NotebookRead,
    summary="Rename or recolor a notebook",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_notebook(
    notebook_id: uuid.UUID,
    payload: NotebookUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotebookRead:
    return NoteNotebookService(db, user.id).update_notebook(notebook_id, payload)


@router.delete(
    "/notebooks/{notebook_id}",
    response_model=OkResponse,
    summary="Delete a notebook (contained notes are kept, moved to no notebook)",
    responses={404: {"model": ErrorResponse}},
)
def delete_notebook(
    notebook_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    NoteNotebookService(db, user.id).delete_notebook(notebook_id)
    return OkResponse(ok=True)


@router.get(
    "/templates",
    response_model=NoteListResponse,
    summary="List note templates",
)
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteListResponse:
    return NoteListResponse(items=NoteService(db, user.id).list_templates())


# --- Baustein-Vorlagen (Feldblöcke) ------------------------------------------
# Bewusst VOR den ``/{note_id}``-Routen definiert, damit „block-templates" nicht
# als Notiz-ID interpretiert wird.
@router.get(
    "/block-templates",
    response_model=NoteBlockTemplateListResponse,
    summary="List block templates (field-box presets)",
)
def list_block_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBlockTemplateListResponse:
    return NoteBlockTemplateListResponse(
        items=NoteBlockTemplateService(db, user.id).list()
    )


@router.post(
    "/block-templates",
    response_model=NoteBlockTemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a block template",
)
def create_block_template(
    payload: NoteBlockTemplateCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBlockTemplateRead:
    template = NoteBlockTemplateService(db, user.id).create(payload)
    return NoteBlockTemplateRead.model_validate(template)


@router.patch(
    "/block-templates/{template_id}",
    response_model=NoteBlockTemplateRead,
    summary="Update a block template",
)
def update_block_template(
    template_id: uuid.UUID,
    payload: NoteBlockTemplateUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteBlockTemplateRead:
    template = NoteBlockTemplateService(db, user.id).update(template_id, payload)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block template not found")
    return NoteBlockTemplateRead.model_validate(template)


@router.delete(
    "/block-templates/{template_id}",
    response_model=OkResponse,
    summary="Delete a block template",
)
def delete_block_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    if not NoteBlockTemplateService(db, user.id).delete(template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block template not found")
    return OkResponse()


@router.post(
    "/from-template/{template_id}",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note from a template",
    responses={404: {"model": ErrorResponse}},
)
def create_note_from_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).create_from_template(template_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vorlage nicht gefunden")
    return NoteRead.model_validate(note)


@router.post(
    "/{note_id}/save-as-template",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save an existing note as a template",
    responses={404: {"model": ErrorResponse}},
)
def save_note_as_template(
    note_id: uuid.UUID,
    payload: SaveAsTemplateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    template = NoteService(db, user.id).save_as_template(note_id, payload.title)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return NoteRead.model_validate(template)


@router.get(
    "/{note_id}/revisions",
    response_model=NoteRevisionListResponse,
    summary="List bundled note revisions",
    responses={404: {"model": ErrorResponse}},
)
def list_note_revisions(
    note_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRevisionListResponse:
    return NoteService(db, user.id).list_revisions(note_id, limit=limit)


@router.get(
    "/{note_id}/revisions/{revision_id}",
    response_model=NoteRevisionRead,
    summary="Get one note revision",
    responses={404: {"model": ErrorResponse}},
)
def get_note_revision(
    note_id: uuid.UUID,
    revision_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRevisionRead:
    return NoteRevisionRead.model_validate(NoteService(db, user.id).get_revision(note_id, revision_id))


@router.post(
    "/{note_id}/revisions/checkpoint",
    response_model=NoteRevisionRead,
    summary="Close the current bundled note revision",
    responses={404: {"model": ErrorResponse}},
)
def checkpoint_note_revision(
    note_id: uuid.UUID,
    payload: NoteRevisionCheckpointRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRevisionRead:
    revision = NoteService(db, user.id).checkpoint_revision(note_id, payload.reason)
    return NoteRevisionRead.model_validate(revision)


@router.post(
    "/{note_id}/revisions/{revision_id}/restore",
    response_model=NoteRead,
    summary="Restore one note revision",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def restore_note_revision(
    note_id: uuid.UUID,
    revision_id: uuid.UUID,
    payload: NoteRevisionRestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).restore_revision(
        note_id,
        revision_id,
        base_revision=payload.base_revision,
    )
    return NoteRead.model_validate(note)


@router.post(
    "/{note_id}/images",
    response_model=NoteImageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image for a note",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
def upload_note_image(
    note_id: uuid.UUID,
    file: UploadFile = File(..., description="JPEG, PNG or WebP image"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteImageRead:
    service = NoteImageService(db, user.id)
    image = service.upload(note_id, file)
    return NoteImageRead(
        id=image.id,
        note_id=image.note_id,
        filename=image.filename,
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        width=image.width,
        height=image.height,
        src=service.image_src(image.note_id, image.id),
    )


@router.get(
    "/{note_id}/images/{image_id}/file",
    response_class=FileResponse,
    summary="Serve a note image",
    responses={404: {"model": ErrorResponse}},
)
def get_note_image(
    note_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    image, path = NoteImageService(db, user.id).get_file(note_id, image_id)
    return FileResponse(
        path=path,
        media_type=image.content_type,
        filename=image.filename,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


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


@router.put(
    "/{note_id}/tags",
    response_model=NoteRead,
    summary="Set the tags of a note (by name; unknown tags are created)",
    responses={404: {"model": ErrorResponse}},
)
def set_note_tags(
    note_id: uuid.UUID,
    payload: NoteTagsUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteRead:
    note = NoteService(db, user.id).set_tags(note_id, tag_ids=payload.tag_ids, names=payload.tags)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    return NoteRead.model_validate(note)


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


@router.post(
    "/{note_id}/tasks/toggle",
    response_model=OkResponse,
    summary="Toggle a note task's done state",
    responses={404: {"model": ErrorResponse}},
)
def toggle_note_task(
    note_id: uuid.UUID,
    payload: NoteTaskToggleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    note = NoteService(db, user.id).set_task_checked(note_id, payload.position, payload.done)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notiz oder Aufgabe nicht gefunden"
        )
    return OkResponse(ok=True)


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
