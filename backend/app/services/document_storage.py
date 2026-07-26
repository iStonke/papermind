"""Dateisystem- und PDF-nahe Operationen für Dokumente, ohne Datenbanklogik."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from pathlib import Path

import pypdfium2 as pdfium
from fastapi import UploadFile
from pypdf import PdfReader

from app.core.errors import BadRequestError, PayloadTooLargeError, StorageError
from app.core.text import sanitize_text_for_db

logger = logging.getLogger("papermind.document_storage")
ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


class DocumentStorageService:
    def __init__(self, *, storage_path: str, upload_max_bytes: int, text_check_pages: int) -> None:
        self.storage_root = Path(storage_path).resolve()
        self.upload_max_bytes = upload_max_bytes
        self.text_check_pages = text_check_pages

    def resolve_path(self, storage_key: str) -> Path:
        candidate = (self.storage_root / storage_key).resolve()
        if self.storage_root != candidate and self.storage_root not in candidate.parents:
            raise StorageError("Invalid storage path")
        return candidate

    @staticmethod
    def relative_file_key(document_id: uuid.UUID, filename: str) -> str:
        return f"{document_id}/{Path(filename).name}"

    @staticmethod
    def cleanup_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
            if path.parent.exists() and not any(path.parent.iterdir()):
                path.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def validate_upload_file(file: UploadFile) -> str:
        filename = (file.filename or "").strip()
        if not filename:
            raise BadRequestError("Filename is missing")
        if not filename.lower().endswith(".pdf"):
            raise BadRequestError("Only .pdf files are allowed")
        if (file.content_type or "").lower() not in ALLOWED_PDF_CONTENT_TYPES:
            raise BadRequestError("Only PDF content types are allowed", details={"content_type": file.content_type})
        return filename

    def inspect_upload_file(self, file: UploadFile) -> tuple[str, int]:
        bytes_read, header_checked, sha256 = 0, False, hashlib.sha256()
        try:
            file.file.seek(0)
            while chunk := file.file.read(1024 * 1024):
                if not header_checked:
                    if not chunk.startswith(b"%PDF-"):
                        raise BadRequestError("File content is not a valid PDF")
                    header_checked = True
                bytes_read += len(chunk)
                if bytes_read > self.upload_max_bytes:
                    raise PayloadTooLargeError("Uploaded file exceeds maximum allowed size", details={"max_bytes": self.upload_max_bytes})
                sha256.update(chunk)
        finally:
            file.file.seek(0)
        if bytes_read == 0:
            raise BadRequestError("Uploaded file is empty")
        if not header_checked:
            raise BadRequestError("File content is not a valid PDF")
        return sha256.hexdigest(), bytes_read

    def store_pdf(self, file: UploadFile, destination: Path) -> int:
        temporary = destination.with_name(f"{destination.name}.uploading")
        bytes_written, header_checked = 0, False
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            file.file.seek(0)
            with temporary.open("wb") as handle:
                while chunk := file.file.read(1024 * 1024):
                    if not header_checked:
                        if not chunk.startswith(b"%PDF-"):
                            raise BadRequestError("File content is not a valid PDF")
                        header_checked = True
                    bytes_written += len(chunk)
                    if bytes_written > self.upload_max_bytes:
                        raise PayloadTooLargeError("Uploaded file exceeds maximum allowed size", details={"max_bytes": self.upload_max_bytes})
                    handle.write(chunk)
            if bytes_written == 0:
                raise BadRequestError("Uploaded file is empty")
            os.replace(temporary, destination)
            return bytes_written
        except (BadRequestError, PayloadTooLargeError):
            temporary.unlink(missing_ok=True)
            raise
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("Failed to write PDF into storage", details=str(exc)) from exc

    def create_thumbnail(self, document_id: uuid.UUID, original_path: Path) -> tuple[str, int, str] | None:
        key = self.relative_file_key(document_id, "thumbnail.png")
        target = self.resolve_path(key)
        temporary = target.with_name("thumbnail.png.generating")
        try:
            pdf = pdfium.PdfDocument(str(original_path))
            if len(pdf) < 1:
                return None
            image = pdf[0].render(scale=0.8).to_pil()
            image.thumbnail((320, 320))
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, target)
            return key, target.stat().st_size, "image/png"
        except Exception as exc:  # noqa: BLE001 - Thumbnail ist optional
            logger.warning("thumbnail generation failed document_id=%s error=%s", document_id, exc)
            temporary.unlink(missing_ok=True)
            return None

    def extract_quick_text_sample(self, pdf_path: Path) -> tuple[str, int, int, int]:
        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
        pages_to_scan = min(total_pages, self.text_check_pages)
        fragments: list[str] = []
        non_whitespace_chars = 0
        for index in range(pages_to_scan):
            text = sanitize_text_for_db(reader.pages[index].extract_text() or "").strip()
            if text:
                fragments.append(text)
                non_whitespace_chars += len(re.sub(r"\s+", "", text))
        return "\n".join(fragments).strip(), non_whitespace_chars, pages_to_scan, total_pages
