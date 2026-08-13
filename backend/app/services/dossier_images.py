"""Validierung und sichere Ablage von Bildern für Leuchttische."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import BadRequestError, PayloadTooLargeError, StorageError


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": {"suffixes": {".jpg", ".jpeg"}, "format": "JPEG", "stored_suffix": ".jpg"},
    "image/png": {"suffixes": {".png"}, "format": "PNG", "stored_suffix": ".png"},
}
MAX_IMAGE_PIXELS = 40_000_000


@dataclass(frozen=True)
class StoredDossierImage:
    filename: str
    content_type: str
    file_key: str
    size_bytes: int
    width: int
    height: int


class DossierImageStorage:
    def __init__(self, *, storage_path: str | None = None, upload_max_bytes: int | None = None) -> None:
        settings = get_settings()
        self.storage_root = Path(storage_path or settings.storage_path).resolve()
        self.upload_max_bytes = int(upload_max_bytes or settings.upload_max_bytes)

    def resolve_path(self, file_key: str) -> Path:
        candidate = (self.storage_root / file_key).resolve()
        if self.storage_root != candidate and self.storage_root not in candidate.parents:
            raise StorageError("Invalid storage path")
        return candidate

    @staticmethod
    def _safe_filename(file: UploadFile) -> str:
        filename = Path((file.filename or "").strip()).name
        if not filename:
            raise BadRequestError("Dateiname fehlt")
        return filename

    def store(self, file: UploadFile, *, owner_id: uuid.UUID, item_id: uuid.UUID) -> StoredDossierImage:
        filename = self._safe_filename(file)
        content_type = (file.content_type or "").lower()
        config = ALLOWED_IMAGE_TYPES.get(content_type)
        suffix = Path(filename).suffix.lower()
        if config is None or suffix not in config["suffixes"]:
            raise BadRequestError("Nur JPEG- und PNG-Bilder sind erlaubt")

        try:
            file.file.seek(0)
            raw = file.file.read(self.upload_max_bytes + 1)
        finally:
            file.file.seek(0)
        if not raw:
            raise BadRequestError("Die Bilddatei ist leer")
        if len(raw) > self.upload_max_bytes:
            raise PayloadTooLargeError(
                "Das Bild überschreitet die maximal erlaubte Dateigröße",
                details={"max_bytes": self.upload_max_bytes},
            )

        file_key = f"dossier-images/{owner_id}/{item_id}{config['stored_suffix']}"
        target = self.resolve_path(file_key)
        temporary = target.with_name(f"{target.name}.uploading")
        try:
            with Image.open(file.file) as source:
                if source.format != config["format"]:
                    raise BadRequestError("Dateiendung, MIME-Typ und Bildinhalt stimmen nicht überein")
                width, height = source.size
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise BadRequestError("Das Bild hat ungültige oder zu große Abmessungen")
                normalized = ImageOps.exif_transpose(source)
                if config["format"] == "JPEG":
                    normalized = normalized.convert("RGB")
                elif normalized.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
                    normalized = normalized.convert("RGBA")
                width, height = normalized.size
                target.parent.mkdir(parents=True, exist_ok=True)
                if config["format"] == "JPEG":
                    normalized.save(temporary, format="JPEG", quality=92, optimize=True)
                else:
                    normalized.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, target)
        except (BadRequestError, PayloadTooLargeError):
            temporary.unlink(missing_ok=True)
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise BadRequestError("Die Datei ist kein gültiges JPEG- oder PNG-Bild") from exc
        except Exception as exc:  # noqa: BLE001 - Dateisystemfehler werden als Storage-Fehler gekapselt
            temporary.unlink(missing_ok=True)
            raise StorageError("Das Bild konnte nicht gespeichert werden", details=str(exc)) from exc

        return StoredDossierImage(
            filename=filename,
            content_type=content_type,
            file_key=file_key,
            size_bytes=target.stat().st_size,
            width=width,
            height=height,
        )

    def cleanup(self, file_key: str) -> None:
        try:
            path = self.resolve_path(file_key)
            path.unlink(missing_ok=True)
            for parent in (path.parent, path.parent.parent):
                if parent.exists() and parent != self.storage_root and not any(parent.iterdir()):
                    parent.rmdir()
        except OSError:
            pass
