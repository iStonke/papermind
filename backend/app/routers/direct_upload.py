"""
Direct Upload Router — für den iOS Shortcut Workflow.

Ein einzelner POST-Endpoint /api/direct-upload, der mit einem statischen
Bearer-Token gesichert ist. Das iPhone schickt eine oder mehrere PDF-Dateien,
die sofort ins Import-Staging eingestellt und automatisch committed werden.
OCR startet anschließend automatisch.
"""

import io
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import verify_shared_upload_api_key
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
_RAW_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


def _filename_to_title(filename: str) -> str:
    """Dateiname ohne Extension als Dokumenttitel."""
    stem = Path(str(filename or "upload").strip()).stem or "Scan"
    title = _INVALID_TITLE_CHARS.sub(" ", stem).strip()
    # Mehrfache Leerzeichen normalisieren
    title = re.sub(r"\s+", " ", title)
    return title[:200] or "Scan"


def _verify_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    verify_shared_upload_api_key(
        request,
        authorization,
        x_api_key,
        service_name="Direct upload",
        rate_limit_bucket="direct_upload",
    )


async def _read_raw_pdf_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.upload_max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded file exceeds maximum allowed size.",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            ) from None

    body = bytearray()
    header_checked = False
    async for chunk in request.stream():
        if not chunk:
            continue

        if not header_checked:
            if not chunk.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File content is not a valid PDF.",
                )
            header_checked = True

        body.extend(chunk)
        if len(body) > settings.upload_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file exceeds maximum allowed size.",
            )

    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leerer Request-Body.",
        )
    if not header_checked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content is not a valid PDF.",
        )

    return bytes(body)


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
        "automatisch. Authentifizierung über X-Api-Key oder Bearer-Token."
        "Akzeptiert multipart/form-data (Feld 'files') oder rohen PDF-Body."
    ),
)
async def direct_upload(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_api_key),
) -> DirectUploadResult:
    content_type = request.headers.get("content-type", "")

    # ── Roher PDF-Body (iOS Shortcut mit Haupttext: Datei) ────────────────────
    if "multipart" not in content_type:
        raw_content_type = content_type.split(";", 1)[0].strip().lower()
        if raw_content_type and raw_content_type not in _RAW_PDF_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Raw uploads must use application/pdf content type.",
            )
        raw = await _read_raw_pdf_body(request)
        fake_file = UploadFile(
            filename="scan.pdf",
            file=io.BytesIO(raw),
            headers={"content-type": "application/pdf"},  # type: ignore[arg-type]
        )
        files = [fake_file]

    # ── Multipart/form-data ───────────────────────────────────────────────────
    else:
        form = await request.form()
        raw_files = form.getlist("files") or form.getlist("file")
        files = [f for f in raw_files if isinstance(f, UploadFile)]
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kein 'files'- oder 'file'-Feld im Formular gefunden.",
            )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mindestens eine Datei ist erforderlich.",
        )

    service = ImportStagingService(db)

    # 1. Alle Dateien ins Staging hochladen
    try:
        staged = service.upload_sources(files)
    except APIError:
        raise
    except Exception as exc:
        logger.error("direct_upload staging failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Staging failed.",
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
    except APIError:
        raise
    except Exception as exc:
        logger.error("direct_upload commit failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Commit failed.",
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
