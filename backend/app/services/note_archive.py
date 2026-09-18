"""Portable, versioned note archives. Import is atomic and never overwrites notes."""
import base64
import copy
import io
import uuid
from datetime import datetime
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import BadRequestError, NotFoundError
from app.models.note import Note, NoteRevision
from app.models.note_collection import NoteCollection
from app.models.note_notebook import NoteNotebook
from app.models.note_image import NoteImage
from app.services.note_images import NoteImageStorage, NoteImageService, ALLOWED_NOTE_IMAGE_TYPES, MAX_NOTE_IMAGE_PIXELS
from app.services.note_service import NoteService, derive_body_text

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


class ArchiveModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Folder(ArchiveModel):
    name: str = Field(min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=32)
    position: int = 0


class Version(ArchiveModel):
    note_revision: int = Field(ge=1)
    reason: Literal['created', 'autosave', 'navigation', 'export', 'ai', 'before_restore', 'restore', 'manual']
    title: str
    body_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class Asset(ArchiveModel):
    id: uuid.UUID
    filename: str
    content_type: Literal['image/jpeg', 'image/png', 'image/webp']
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    created_at: datetime
    data: str


class NoteArchive(ArchiveModel):
    format: Literal['papermind-note']
    version: Literal[1]
    source_id: uuid.UUID
    title: str = Field(max_length=500)
    body_json: dict[str, Any]
    revision: int = Field(ge=1)
    is_template: bool
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    tags: list[str]
    collection: Folder | None
    notebook: Folder | None
    history: list[Version]
    images: list[Asset]


def rewrite_body(body, source_id, target_id, images, *, drop_missing_images=False):
    if body.get('type') != 'doc':
        raise BadRequestError('Die Notizstruktur muss ein Dokument sein')
    result = copy.deepcopy(body)

    def rewrite_node(node):
        if not isinstance(node, dict):
            raise BadRequestError('Ungültige Notizstruktur')
        attrs = node.get('attrs') or {}
        if node.get('type') == 'image' and attrs.get('imageId'):
            image_id = images.get(str(attrs['imageId']))
            if image_id is None:
                if drop_missing_images:
                    return None
                raise BadRequestError('Das Archiv enthält nicht alle Bilder')
            attrs.update(imageId=str(image_id), noteId=str(target_id),
                         src=NoteImageService.image_src(target_id, image_id))
        if node.get('type') == 'wikiLink' and attrs.get('targetType') == 'note' and attrs.get('targetId') == str(source_id):
            attrs['targetId'] = str(target_id)
        # Self-links must point to the newly imported note, external links stay intact.
        for mark in node.get('marks') or []:
            mark_attrs = mark.get('attrs') or {}
            if mark_attrs.get('href') == f'papermind://note/{source_id}':
                mark_attrs['href'] = f'papermind://note/{target_id}'
        content = node.get('content')
        if content is not None:
            if not isinstance(content, list):
                raise BadRequestError('Ungültige Notizstruktur')
            node['content'] = [
                rewritten
                for child in content
                if (rewritten := rewrite_node(child)) is not None
            ]
        return node

    return rewrite_node(result)


class NoteArchiveService:
    def __init__(self, db, owner_id):
        self.db = db
        self.owner_id = owner_id
        self.notes = NoteService(db, owner_id)
        self.storage = NoteImageStorage()

    def export(self, note_id):
        note = self.notes.get_note(note_id)
        if note is None:
            raise NotFoundError('Notiz nicht gefunden')
        def folder(model, key):
            row = self.db.scalar(select(model).where(model.id == key, model.owner_id == self.owner_id)) if key else None
            return Folder(name=row.name, color=row.color, position=row.position) if row else None
        history = self.db.scalars(select(NoteRevision).where(
            NoteRevision.note_id == note_id, NoteRevision.owner_id == self.owner_id
        ).order_by(NoteRevision.note_revision)).all()
        rows = self.db.scalars(select(NoteImage).where(
            NoteImage.note_id == note_id, NoteImage.owner_id == self.owner_id)).all()
        images = []
        total = 0
        for row in rows:
            path = self.storage.resolve_path(row.file_key)
            if not path.is_file():
                raise BadRequestError('Eine Bilddatei fehlt. Vollständiger Export nicht möglich.')
            total += path.stat().st_size
            if total > MAX_ARCHIVE_BYTES * 3 // 4:
                raise BadRequestError('Die Notiz ist für den Export zu groß (100 MB).')
            images.append(Asset(id=row.id, filename=row.filename, content_type=row.content_type,
                                width=row.width, height=row.height, created_at=row.created_at,
                                data=base64.b64encode(path.read_bytes()).decode('ascii')))
        archive = NoteArchive(format='papermind-note', version=1, source_id=note.id,
            title=note.title, body_json=note.body_json, revision=note.revision,
            is_template=note.is_template, is_favorite=note.is_favorite,
            created_at=note.created_at, updated_at=note.updated_at,
            tags=[tag.name for tag in note.tags],
            collection=folder(NoteCollection, note.collection_id),
            notebook=folder(NoteNotebook, note.notebook_id),
            history=[Version(**{key: getattr(row, key) for key in Version.model_fields}) for row in history],
            images=images)
        mapping = {str(row.id): row.id for row in rows}
        for body in [archive.body_json, *(v.body_json for v in archive.history)]:
            rewritten = rewrite_body(
                body,
                note.id,
                note.id,
                mapping,
                drop_missing_images=True,
            )
            body.clear()
            body.update(rewritten)
        return archive

    def import_archive(self, archive):
        if not archive.is_template and archive.collection is None:
            raise BadRequestError('Die Sammlung fehlt im Archiv')
        if len({v.note_revision for v in archive.history}) != len(archive.history) or any(v.note_revision > archive.revision for v in archive.history):
            raise BadRequestError('Ungültiger Versionsverlauf')
        note_id = uuid.uuid4()
        mapping = {str(asset.id): uuid.uuid4() for asset in archive.images}
        if len(mapping) != len(archive.images):
            raise BadRequestError('Doppelte Bilder im Archiv')
        body = rewrite_body(archive.body_json, archive.source_id, note_id, mapping)
        versions = [(v, rewrite_body(v.body_json, archive.source_id, note_id, mapping)) for v in archive.history]
        # Verify every image before writing anything; preserve the original bytes.
        decoded = []
        try:
            for asset in archive.images:
                raw = base64.b64decode(asset.data, validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != ALLOWED_NOTE_IMAGE_TYPES[asset.content_type]['format'] or image.size != (asset.width, asset.height) or asset.width * asset.height > MAX_NOTE_IMAGE_PIXELS:
                        raise ValueError('Invalid image')
                    image.verify()
                decoded.append((asset, raw))
        except Exception as exc:
            raise BadRequestError('Das Archiv enthält ein ungültiges Bild') from exc
        keys = []
        try:
            def restore_folder(model, value, collection_id=None):
                if value is None:
                    return None
                query = select(model).where(model.owner_id == self.owner_id, model.name == value.name)
                if model is NoteNotebook:
                    query = query.where(model.collection_id == collection_id)
                row = self.db.scalar(query)
                if row is None:
                    row = model(id=uuid.uuid4(), owner_id=self.owner_id, **value.model_dump())
                    if model is NoteNotebook:
                        row.collection_id = collection_id
                    self.db.add(row)
                    self.db.flush()
                return row.id
            collection_id = restore_folder(NoteCollection, archive.collection) if not archive.is_template else None
            notebook_id = restore_folder(NoteNotebook, archive.notebook, collection_id) if collection_id else None
            note = Note(id=note_id, owner_id=self.owner_id, title=archive.title,
                body_json=body, body_text=derive_body_text(body), revision=archive.revision,
                is_template=archive.is_template, is_favorite=archive.is_favorite,
                collection_id=collection_id, notebook_id=notebook_id, is_deleted=False,
                created_at=archive.created_at, updated_at=archive.updated_at)
            self.db.add(note)
            self.db.flush()
            note.tags = [tag for name in archive.tags if (tag := self.notes._get_or_create_tag(name)) is not None]
            for asset, raw in decoded:
                image_id = mapping[str(asset.id)]
                key = self.storage.file_key(self.owner_id, note_id, image_id,
                    ALLOWED_NOTE_IMAGE_TYPES[asset.content_type]['stored_suffix'])
                keys.append(key)
                path = self.storage.resolve_path(key)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                self.db.add(NoteImage(id=image_id, owner_id=self.owner_id, note_id=note_id,
                    file_key=key, filename=asset.filename, content_type=asset.content_type,
                    size_bytes=len(raw), width=asset.width, height=asset.height, created_at=asset.created_at))
            for version, version_body in versions:
                values = version.model_dump(exclude={'body_json'})
                self.db.add(NoteRevision(id=uuid.uuid4(), owner_id=self.owner_id, note_id=note_id,
                    body_json=version_body, body_text=derive_body_text(version_body), **values))
            if not note.is_template:
                self.notes._sync_links(note)
                self.notes._sync_tasks(note)
            from sqlalchemy.orm.attributes import flag_modified
            note.updated_at = archive.updated_at
            flag_modified(note, "updated_at")
            self.db.commit()
            self.db.refresh(note)
            return note
        except Exception:
            self.db.rollback()
            for key in keys:
                self.storage.cleanup(key)
            raise
