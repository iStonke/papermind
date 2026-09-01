import io
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from PIL import Image

from app.core.deps import _allows_file_query_token
from app.core.errors import BadRequestError
from app.services.note_images import NoteImageService, NoteImageStorage
from app.services.note_service import derive_body_text


def _image_upload(filename: str, content_type: str, *, image_format: str = "PNG") -> UploadFile:
    raw = io.BytesIO()
    Image.new("RGB", (24, 16), color=(20, 120, 130)).save(raw, format=image_format)
    raw.seek(0)
    return UploadFile(filename=filename, file=raw, headers={"content-type": content_type})


def test_note_image_storage_validates_and_normalizes_png(tmp_path: Path) -> None:
    storage = NoteImageStorage(storage_path=str(tmp_path), upload_max_bytes=1024 * 1024)
    owner_id = uuid.uuid4()
    note_id = uuid.uuid4()
    image_id = uuid.uuid4()

    stored = storage.store(
        _image_upload("Grafik.png", "image/png"),
        owner_id=owner_id,
        note_id=note_id,
        image_id=image_id,
    )

    assert stored.width == 24
    assert stored.height == 16
    assert stored.file_key == f"note-images/{owner_id}/{note_id}/{image_id}.png"
    assert storage.resolve_path(stored.file_key).is_file()


def test_note_image_storage_rejects_mismatched_content(tmp_path: Path) -> None:
    storage = NoteImageStorage(storage_path=str(tmp_path), upload_max_bytes=1024 * 1024)
    with pytest.raises(BadRequestError):
        storage.store(
            _image_upload("Foto.png", "image/png", image_format="JPEG"),
            owner_id=uuid.uuid4(),
            note_id=uuid.uuid4(),
            image_id=uuid.uuid4(),
        )


def test_cloning_a_note_rewrites_image_references_and_copies_the_file(tmp_path: Path) -> None:
    owner_id = uuid.uuid4()
    source_note_id = uuid.uuid4()
    target_note_id = uuid.uuid4()
    source_image_id = uuid.uuid4()
    storage = NoteImageStorage(storage_path=str(tmp_path), upload_max_bytes=1024 * 1024)
    stored = storage.store(
        _image_upload("Skizze.png", "image/png"),
        owner_id=owner_id,
        note_id=source_note_id,
        image_id=source_image_id,
    )
    source = SimpleNamespace(
        id=source_image_id,
        filename=stored.filename,
        content_type=stored.content_type,
        file_key=stored.file_key,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
    )

    class FakeSession:
        def __init__(self):
            self.created = []

        def scalars(self, _statement):
            return SimpleNamespace(all=lambda: [source])

        def add(self, value):
            self.created.append(value)

    db = FakeSession()
    service = NoteImageService(db, owner_id)
    service.storage = storage
    body = {
        "type": "doc",
        "content": [{
            "type": "image",
            "attrs": {
                "src": NoteImageService.image_src(source_note_id, source_image_id),
                "noteId": str(source_note_id),
                "imageId": str(source_image_id),
                "caption": "Grundriss",
            },
        }],
    }

    cloned, file_keys = service.clone_body_images(
        body,
        source_note_id=source_note_id,
        target_note_id=target_note_id,
    )

    attrs = cloned["content"][0]["attrs"]
    assert attrs["imageId"] != str(source_image_id)
    assert attrs["noteId"] == str(target_note_id)
    assert attrs["src"] == NoteImageService.image_src(target_note_id, uuid.UUID(attrs["imageId"]))
    assert len(db.created) == 1
    assert len(file_keys) == 1
    assert storage.resolve_path(file_keys[0]).is_file()


def test_image_caption_contributes_to_note_search_text() -> None:
    body = {
        "type": "doc",
        "content": [{"type": "image", "attrs": {"caption": "Zählerstand August"}}],
    }
    assert derive_body_text(body) == "Zählerstand August"


def test_note_image_routes_and_file_token_scope_are_registered() -> None:
    from app.routers.notes import router

    paths = {route.path: route.methods for route in router.routes}
    assert "POST" in paths["/api/notes/{note_id}/images"]
    assert "GET" in paths["/api/notes/{note_id}/images/{image_id}/file"]
    assert _allows_file_query_token(
        "GET",
        f"/api/notes/{uuid.uuid4()}/images/{uuid.uuid4()}/file",
    )
