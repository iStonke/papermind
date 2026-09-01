"""Validation, storage and owner-scoped access for note image assets."""

from __future__ import annotations

import copy
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError, StorageError
from app.models.note import Note
from app.models.note_image import NoteImage


ALLOWED_NOTE_IMAGE_TYPES = {
    "image/jpeg": {"suffixes": {".jpg", ".jpeg"}, "format": "JPEG", "stored_suffix": ".jpg"},
    "image/png": {"suffixes": {".png"}, "format": "PNG", "stored_suffix": ".png"},
    "image/webp": {"suffixes": {".webp"}, "format": "WEBP", "stored_suffix": ".webp"},
}
MAX_NOTE_IMAGE_PIXELS = 40_000_000


@dataclass(frozen=True)
class StoredNoteImage:
    filename: str
    content_type: str
    file_key: str
    size_bytes: int
    width: int
    height: int


class NoteImageStorage:
    def __init__(self, *, storage_path: str | None = None, upload_max_bytes: int | None = None) -> None:
        settings = get_settings()
        self.storage_root = Path(storage_path or settings.storage_path).resolve()
        self.upload_max_bytes = int(upload_max_bytes or settings.upload_max_bytes)

    def resolve_path(self, file_key: str) -> Path:
        candidate = (self.storage_root / file_key).resolve()
        if self.storage_root != candidate and self.storage_root not in candidate.parents:
            raise StorageError("Ungültiger Speicherpfad")
        return candidate

    @staticmethod
    def _safe_filename(file: UploadFile) -> str:
        filename = Path((file.filename or "").strip()).name
        if not filename:
            raise BadRequestError("Dateiname fehlt")
        return filename

    @staticmethod
    def file_key(
        owner_id: uuid.UUID,
        note_id: uuid.UUID,
        image_id: uuid.UUID,
        suffix: str,
    ) -> str:
        return f"note-images/{owner_id}/{note_id}/{image_id}{suffix}"

    def store(
        self,
        file: UploadFile,
        *,
        owner_id: uuid.UUID,
        note_id: uuid.UUID,
        image_id: uuid.UUID,
    ) -> StoredNoteImage:
        filename = self._safe_filename(file)
        content_type = (file.content_type or "").lower()
        config = ALLOWED_NOTE_IMAGE_TYPES.get(content_type)
        suffix = Path(filename).suffix.lower()
        if config is None or suffix not in config["suffixes"]:
            raise BadRequestError("Nur JPEG-, PNG- und WebP-Bilder sind erlaubt")

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

        file_key = self.file_key(
            owner_id,
            note_id,
            image_id,
            str(config["stored_suffix"]),
        )
        target = self.resolve_path(file_key)
        temporary = target.with_name(f"{target.name}.uploading")
        try:
            with Image.open(file.file) as source:
                if source.format != config["format"]:
                    raise BadRequestError("Dateiendung, MIME-Typ und Bildinhalt stimmen nicht überein")
                width, height = source.size
                if width < 1 or height < 1 or width * height > MAX_NOTE_IMAGE_PIXELS:
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
                elif config["format"] == "WEBP":
                    normalized.save(temporary, format="WEBP", quality=92, method=4)
                else:
                    normalized.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, target)
        except (BadRequestError, PayloadTooLargeError):
            temporary.unlink(missing_ok=True)
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            raise BadRequestError("Die Datei ist kein gültiges JPEG-, PNG- oder WebP-Bild") from exc
        except Exception as exc:  # noqa: BLE001 - storage failures are normalized
            temporary.unlink(missing_ok=True)
            raise StorageError("Das Bild konnte nicht gespeichert werden", details=str(exc)) from exc

        return StoredNoteImage(
            filename=filename,
            content_type=content_type,
            file_key=file_key,
            size_bytes=target.stat().st_size,
            width=width,
            height=height,
        )

    def clone(
        self,
        source_key: str,
        *,
        owner_id: uuid.UUID,
        note_id: uuid.UUID,
        image_id: uuid.UUID,
    ) -> str:
        source = self.resolve_path(source_key)
        if not source.is_file():
            raise StorageError("Die Bilddatei zum Kopieren wurde nicht gefunden")
        suffix = source.suffix.lower()
        if suffix not in {".jpg", ".png", ".webp"}:
            raise StorageError("Das Bildformat kann nicht kopiert werden")
        file_key = self.file_key(owner_id, note_id, image_id, suffix)
        target = self.resolve_path(file_key)
        temporary = target.with_name(f"{target.name}.copying")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        except Exception as exc:  # noqa: BLE001 - storage failures are normalized
            temporary.unlink(missing_ok=True)
            raise StorageError("Das Bild konnte nicht kopiert werden", details=str(exc)) from exc
        return file_key

    def cleanup(self, file_key: str) -> None:
        try:
            path = self.resolve_path(file_key)
            path.unlink(missing_ok=True)
            current = path.parent
            stop = self.storage_root / "note-images"
            while current != self.storage_root and current != stop.parent:
                if not current.exists() or any(current.iterdir()):
                    break
                current.rmdir()
                current = current.parent
        except OSError:
            pass


class NoteImageService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None) -> None:
        self.db = db
        self.owner_id = owner_id
        self.storage = NoteImageStorage()

    @staticmethod
    def image_src(note_id: uuid.UUID, image_id: uuid.UUID) -> str:
        return f"/api/notes/{note_id}/images/{image_id}/file"

    def _note(self, note_id: uuid.UUID, *, include_deleted: bool = False) -> Note | None:
        stmt = select(Note).where(Note.id == note_id, Note.owner_id == self.owner_id)
        if not include_deleted:
            stmt = stmt.where(Note.is_deleted.is_(False))
        return self.db.scalar(stmt)

    def upload(self, note_id: uuid.UUID, file: UploadFile) -> NoteImage:
        if self.owner_id is None:
            raise BadRequestError("Für Bild-Uploads ist ein Benutzer erforderlich")
        if self._note(note_id) is None:
            raise NotFoundError("Notiz nicht gefunden", details={"note_id": str(note_id)})
        image_id = uuid.uuid4()
        stored = self.storage.store(
            file,
            owner_id=self.owner_id,
            note_id=note_id,
            image_id=image_id,
        )
        image = NoteImage(
            id=image_id,
            note_id=note_id,
            owner_id=self.owner_id,
            filename=stored.filename,
            content_type=stored.content_type,
            file_key=stored.file_key,
            size_bytes=stored.size_bytes,
            width=stored.width,
            height=stored.height,
        )
        self.db.add(image)
        try:
            self.db.commit()
            self.db.refresh(image)
        except Exception:
            self.db.rollback()
            self.storage.cleanup(stored.file_key)
            raise
        return image

    def get_file(self, note_id: uuid.UUID, image_id: uuid.UUID) -> tuple[NoteImage, Path]:
        image = self.db.scalar(
            select(NoteImage).where(
                NoteImage.id == image_id,
                NoteImage.note_id == note_id,
                NoteImage.owner_id == self.owner_id,
            )
        )
        if image is None:
            raise NotFoundError("Bild nicht gefunden", details={"image_id": str(image_id)})
        path = self.storage.resolve_path(image.file_key)
        if not path.is_file():
            raise NotFoundError("Bilddatei nicht gefunden", details={"image_id": str(image_id)})
        return image, path

    def clone_body_images(
        self,
        body_json: dict[str, Any],
        *,
        source_note_id: uuid.UUID,
        target_note_id: uuid.UUID,
    ) -> tuple[dict[str, Any], list[str]]:
        """Copy image assets referenced by ``body_json`` and rewrite their attrs."""

        cloned = copy.deepcopy(body_json)
        if self.owner_id is None:
            return cloned, []
        source_rows = self.db.scalars(
            select(NoteImage).where(
                NoteImage.note_id == source_note_id,
                NoteImage.owner_id == self.owner_id,
            )
        ).all()
        by_id = {str(row.id): row for row in source_rows}
        copied: dict[str, NoteImage] = {}
        created_keys: list[str] = []

        def walk(node: Any) -> None:
            if not isinstance(node, dict):
                return
            if node.get("type") == "image":
                attrs = node.get("attrs")
                if isinstance(attrs, dict):
                    source_id = str(attrs.get("imageId") or "")
                    source = by_id.get(source_id)
                    if source is not None:
                        image = copied.get(source_id)
                        if image is None:
                            new_id = uuid.uuid4()
                            new_key = self.storage.clone(
                                source.file_key,
                                owner_id=self.owner_id,
                                note_id=target_note_id,
                                image_id=new_id,
                            )
                            created_keys.append(new_key)
                            image = NoteImage(
                                id=new_id,
                                note_id=target_note_id,
                                owner_id=self.owner_id,
                                filename=source.filename,
                                content_type=source.content_type,
                                file_key=new_key,
                                size_bytes=source.size_bytes,
                                width=source.width,
                                height=source.height,
                            )
                            self.db.add(image)
                            copied[source_id] = image
                        attrs["imageId"] = str(image.id)
                        attrs["noteId"] = str(target_note_id)
                        attrs["src"] = self.image_src(target_note_id, image.id)
            for child in node.get("content") or []:
                walk(child)

        try:
            walk(cloned)
        except Exception:
            for file_key in created_keys:
                self.storage.cleanup(file_key)
            raise
        return cloned, created_keys
