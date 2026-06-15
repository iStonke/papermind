import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.documents import (
    DocumentCreateRequest,
    DocumentDetail,
    DocumentFileRole,
    DocumentListResponse,
    DocumentMetadataSuggestion,
    DocumentSortField,
    DocumentStatus,
    DocumentTagReplaceRequest,
    DocumentUpdateRequest,
    SortOrder,
)
from app.schemas.retrieval import DocumentChunkListResponse, DocumentChunkDebugRead, DocumentEmbeddingStatusResponse
from app.services.documents import DocumentService
from app.services.embeddings import EmbeddingService

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents with filters and pagination",
    responses={422: {"model": ErrorResponse}},
)
def list_documents(
    q: str | None = Query(
        default=None,
        description="Full-text search in filename, notes and OCR text (language configurable via FTS_LANGUAGE)",
    ),
    tag: str | None = Query(default=None, description="Filter by tag UUID or exact tag name"),
    tag_id: uuid.UUID | None = Query(default=None, description="Filter by tag UUID (preferred)"),
    tag_ids: list[uuid.UUID] = Query(default_factory=list, description="Filter by multiple tag UUIDs (all must match)"),
    untagged: bool = Query(default=False, description="Filter only documents without any tag assignment"),
    document_type: str | None = Query(
        default=None,
        description="Filter by document type / category name (exact, case-insensitive)",
    ),
    status_filter: DocumentStatus | None = Query(
        default=None,
        alias="status",
        description="Filter by document status",
    ),
    date_from: date | None = Query(default=None, description="Filter documents from document_date"),
    date_to: date | None = Query(default=None, description="Filter documents until document_date"),
    recent_imports: bool = Query(
        default=False,
        description="Filter by recent import window based on created_at and global settings",
    ),
    in_trash: bool = Query(default=False, description="Show documents in trash (is_deleted=true)"),
    favorites_only: bool = Query(default=False, description="Show only favorite documents"),
    sort: DocumentSortField = Query(default=DocumentSortField.created_at, description="Sort field"),
    order: SortOrder = Query(default=SortOrder.desc, description="Sort order"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> DocumentListResponse:
    service = DocumentService(db, user.id)
    effective_tag = str(tag_id) if tag_id is not None else tag
    return service.list_documents(
        q=q,
        tag=effective_tag,
        tag_ids=tag_ids,
        untagged=untagged,
        document_type=document_type,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        recent_imports=recent_imports,
        in_trash=in_trash,
        favorites_only=favorites_only,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/upload",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF and create document record",
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def upload_document(
    file: UploadFile = File(..., description="PDF file"),
    document_date: date | None = Form(default=None),
    doc_date: date | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> DocumentDetail:
    service = DocumentService(db, user.id)
    effective_document_date = document_date if document_date is not None else doc_date
    document = service.upload_document(file=file, document_date=effective_document_date, notes=notes)
    return service.as_detail(service.get_document_or_404(document.id))


@router.post(
    "/{document_id}/ocr",
    response_model=DocumentDetail,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue OCR job for a document",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def queue_document_ocr(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.queue_ocr_for_document(document_id))


@router.post(
    "/ocr-backfill",
    summary="Queue OCR jobs for documents that have no OCR yet (close gaps)",
)
def backfill_ocr(
    dry_run: bool = Query(
        default=False,
        description="If true, only report which documents would be queued (no jobs created).",
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=1000,
        description="Maximum number of OCR jobs to queue in this call.",
    ),
    include_failed: bool = Query(
        default=True,
        description="Also retry documents whose previous OCR failed (bounded by the retry limit).",
    ),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    config = get_settings()
    service = DocumentService(db, user.id)
    return service.backfill_ocr(
        limit=limit,
        include_failed=include_failed,
        max_retries=config.ocr_backfill_max_retries,
        dry_run=dry_run,
    )


@router.post(
    "/{document_id}/index",
    response_model=DocumentDetail,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue indexing/embedding job for a document",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def queue_document_index(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="Force re-index by clearing cached text hash"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.queue_index_for_document(document_id, force=force))


@router.post(
    "/{document_id}/auto-tags",
    response_model=DocumentDetail,
    summary="Analyze document text and apply tags conservatively",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def auto_tag_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.auto_tag_document(document_id))


@router.post(
    "/{document_id}/ai-metadata",
    response_model=DocumentMetadataSuggestion,
    summary="Suggest metadata fields (name, date, document type, notes, tags) via AI",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def suggest_document_metadata(
    document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DocumentMetadataSuggestion:
    service = DocumentService(db, user.id)
    return service.suggest_metadata(document_id)


@router.post(
    "",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create metadata-only document",
    responses={422: {"model": ErrorResponse}},
)
def create_document(payload: DocumentCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    document = service.create_document(payload)
    return service.as_detail(service.get_document_or_404(document.id))


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Get document details",
    responses={404: {"model": ErrorResponse}},
)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.get_document_or_404(document_id))


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="List indexed chunks for a document (debug)",
    responses={404: {"model": ErrorResponse}},
)
def get_document_chunks(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentChunkListResponse:
    service = EmbeddingService(db, user.id)
    chunks = service.list_document_chunks(document_id)
    return DocumentChunkListResponse(
        document_id=document_id,
        chunk_count=len(chunks),
        items=[
                DocumentChunkDebugRead(
                    id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    page_from=chunk.page_from,
                    page_to=chunk.page_to,
                    chunk_type=chunk.chunk_type,
                    char_len=chunk.char_len,
                    token_len=chunk.token_len,
                    content_hash=chunk.content_hash,
                )
            for chunk in chunks
        ],
    )


@router.get(
    "/{document_id}/embedding-status",
    response_model=DocumentEmbeddingStatusResponse,
    summary="Get embedding status and counters for a document (debug)",
    responses={404: {"model": ErrorResponse}},
)
def get_document_embedding_status(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentEmbeddingStatusResponse:
    service = EmbeddingService(db, user.id)
    data = service.get_embedding_status(document_id)
    return DocumentEmbeddingStatusResponse.model_validate(data)


@router.post(
    "/{document_id}/mark-viewed",
    response_model=OkResponse,
    summary="Mark document as viewed",
    responses={404: {"model": ErrorResponse}},
)
def mark_document_viewed(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    service = DocumentService(db, user.id)
    service.mark_document_viewed(document_id)
    return OkResponse(ok=True)


@router.get(
    "/{document_id}/file",
    summary="Download/stream document file by role",
    responses={404: {"model": ErrorResponse}},
)
def get_document_file(
    document_id: uuid.UUID,
    role: DocumentFileRole = Query(default=DocumentFileRole.original, description="File role to serve"),
    download: bool = Query(default=False, description="Force download as attachment"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> FileResponse:
    service = DocumentService(db, user.id)
    document, file_record, file_path = service.get_document_file_by_role(document_id, role)
    download_name = file_record.filename or document.original_filename or "document.bin"
    return FileResponse(
        path=file_path,
        media_type=file_record.mime_type,
        filename=download_name,
        content_disposition_type="attachment" if download else "inline",
        # Browser-Caching der Vorschau: Dateiinhalt je Dokument/Rolle ist nahezu
        # statisch. `private` (per-Benutzer, authentifiziert), kurzes max-age als
        # Kompromiss zur Frische nach erneutem OCR. Spart auf dem Pi den wiederholten
        # Voll-Download. ETag/Last-Modified von FileResponse bleiben für Revalidierung.
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/{document_id}/thumbnail",
    summary="Serve document thumbnail",
    responses={404: {"model": ErrorResponse}},
)
def get_document_thumbnail(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> FileResponse:
    service = DocumentService(db, user.id)
    _, file_record, file_path = service.get_document_file_by_role(document_id, DocumentFileRole.thumbnail)
    return FileResponse(
        path=file_path,
        media_type=file_record.mime_type,
        filename=file_record.filename or "thumbnail.png",
        content_disposition_type="inline",
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Update document metadata",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdateRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.update_document(document_id, payload))


@router.post(
    "/{document_id}/trash",
    response_model=DocumentDetail,
    status_code=status.HTTP_200_OK,
    summary="Move document to trash (soft delete)",
    responses={404: {"model": ErrorResponse}},
)
def trash_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.trash_document(document_id))


@router.post(
    "/{document_id}/restore",
    response_model=DocumentDetail,
    status_code=status.HTTP_200_OK,
    summary="Restore document from trash",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
def restore_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.restore_document(document_id))


@router.post(
    "/{document_id}/favorite",
    response_model=DocumentDetail,
    status_code=status.HTTP_200_OK,
    summary="Toggle favorite status",
    responses={404: {"model": ErrorResponse}},
)
def toggle_favorite(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.toggle_favorite(document_id))


@router.delete(
    "/trash",
    summary="Permanently delete all documents in trash",
)
def empty_trash(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, int | bool]:
    service = DocumentService(db, user.id)
    deleted_count = service.empty_trash()
    return {"ok": True, "deleted_count": deleted_count}


@router.delete(
    "/{document_id}",
    response_model=OkResponse,
    summary="Permanently delete document (also works for trashed documents)",
    responses={404: {"model": ErrorResponse}},
)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    service = DocumentService(db, user.id)
    service.delete_document(document_id)
    return OkResponse(ok=True)


@router.post(
    "/{document_id}/tags",
    response_model=DocumentDetail,
    summary="Replace document tags by tag IDs",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def replace_document_tags(
    document_id: uuid.UUID,
    payload: DocumentTagReplaceRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.replace_document_tags(document_id, payload))


@router.delete(
    "/{document_id}/tags/{tag_id}",
    response_model=DocumentDetail,
    summary="Remove one tag relation from a document",
    responses={404: {"model": ErrorResponse}},
)
def remove_document_tag(document_id: uuid.UUID, tag_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DocumentDetail:
    service = DocumentService(db, user.id)
    return service.as_detail(service.remove_document_tag(document_id, tag_id))
