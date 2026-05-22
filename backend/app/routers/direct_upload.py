"""
Direct Upload Router — für den iOS Shortcut Workflow.

Ein einzelner POST-Endpoint /api/direct-upload, der mit einem statischen
Bearer-Token gesichert ist. Das iPhone schickt eine oder mehrere PDF-Dateien,
die sofort ins Import-Staging eingestellt und automatisch committed werden.
OCR startet anschließend automatisch.
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.schemas.import_staging import (
    ImportCommitDocumentInput,
    ImportCommitOptions,
    ImportCommitPageInput,
    ImportCommitRequest,
)
from app.services.import_staging import ImportStagingService

logger = logging.getLogger("papermind.direct_upload")
settings = get_settings()

router = APIRouter(tags=["Direct Upload"])

_INVALID_TITLE_CHARS = re.compile(r'[\/\\:*?"<>|]+')


def _filename_to_title(filename: str) -> str:
    """Dateiname ohne Extension als Dokumenttitel."""
    stem = Path(str(filename or "upload").strip()).stem or "Scan"
    title = _INVALID_TITLE_CHARS.sub(" ", stem).strip()
    # Mehrfache Leerzeichen normalisieren
    title = re.sub(r"\s+", " ", title)
    return title[:200] or "Scan"


def _verify_api_key(authorization: str | None = Header(default=None)) -> None:
    """Prüft den Bearer-Token gegen DIRECT_UPLOAD_API_KEY aus der .env."""
    configured_key = settings.direct_upload_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Direct upload is not configured (DIRECT_UPLOAD_API_KEY not set).",
        )
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token.strip() != configured_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )


class DirectUploadResult(BaseModel):
    uploaded: int = Field(description="Anzahl hochgeladener Dateien")
    committed: int = Field(description="Anzahl erstellter Dokumente")
    errors: int = Field(description="Anzahl fehlgeschlagener Dateien")
    documents: list[dict] = Field(
        default_factory=list,
        description="Erstellte Dokumente mit doc_id und title",
    )
    error_details: list[str] = Field(
        default_factory=list,
        description="Fehlermeldungen für fehlgeschlagene Dateien",
    )


@router.post(
    "/api/direct-upload",
    response_model=DirectUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Direkt-Upload für iOS Shortcut — PDF(s) werden sofort importiert",
    description=(
        "Nimmt eine oder mehrere PDF-Dateien entgegen, stellt sie in das "
        "Import-Staging ein und committed sie automatisch. OCR startet danach "
        "automatisch. Authentifizierung über Bearer-Token (DIRECT_UPLOAD_API_KEY)."
    ),
)
def direct_upload(
    files: list[UploadFile] = File(..., description="Ein oder mehrere PDF-Dateien"),
    db: Session = Depends(get_db),
    _: None = Depends(_verify_api_key),
) -> DirectUploadResult:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mindestens eine Datei ist erforderlich.",
        )

    service = ImportStagingService(db)

    # 1. Alle Dateien ins Staging hochladen
    try:
        staged = service.upload_sources(files)
    except Exception as exc:
        logger.error("direct_upload staging failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Staging fehlgeschlagen: {exc}",
        ) from exc

    if not staged.items:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Keine Dateien konnten ins Staging gestellt werden.",
        )

    logger.info("direct_upload staged %d file(s)", len(staged.items))

    # 2. Für jede Staging-Datei ein Dokument mit allen Seiten committen
    commit_documents: list[ImportCommitDocumentInput] = []
    filename_map: dict[str, str] = {}

    for item in staged.items:
        # Original-Dateinamen für den Titel merken
        title = _filename_to_title(item.original_name)
        filename_map[item.source_file_id] = title
        pages = [
            ImportCommitPageInput(
                source_file_id=item.source_file_id,
                page_index=page_idx,
                rotation=0,
            )
            for page_idx in range(item.page_count)
        ]
        commit_documents.append(
            ImportCommitDocumentInput(title=title, tag_ids=[], pages=pages)
        )

    commit_request = ImportCommitRequest(
        documents=commit_documents,
        options=ImportCommitOptions(auto_ocr=True, auto_index=True, auto_embed=True),
    )

    try:
        commit_result = service.commit(commit_request)
    except Exception as exc:
        logger.error("direct_upload commit failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Commit fehlgeschlagen: {exc}",
        ) from exc

    created_docs = [
        {"doc_id": item.doc_id, "title": item.title, "page_count": item.page_count}
        for item in commit_result.created
    ]
    error_details = [err.message for err in commit_result.errors]

    logger.info(
        "direct_upload complete uploaded=%d committed=%d errors=%d",
        len(staged.items),
        len(created_docs),
        len(error_details),
    )

    return DirectUploadResult(
        uploaded=len(staged.items),
        committed=len(created_docs),
        errors=len(error_details),
        documents=created_docs,
        error_details=error_details,
    )
