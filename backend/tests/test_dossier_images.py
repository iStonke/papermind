import tempfile
import unittest
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.core.errors import BadRequestError
from app.services.dossier_images import DossierImageStorage


def _image_upload(*, filename: str, content_type: str, format_name: str) -> UploadFile:
    payload = BytesIO()
    Image.new("RGB", (48, 32), (38, 143, 132)).save(payload, format=format_name)
    payload.seek(0)
    return UploadFile(
        filename=filename,
        file=payload,
        headers=Headers({"content-type": content_type}),
    )


class DossierImageStorageTest(unittest.TestCase):
    def test_stores_normalized_jpeg_and_png_inside_the_storage_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = DossierImageStorage(storage_path=directory, upload_max_bytes=1024 * 1024)
            owner_id = uuid.uuid4()
            for filename, content_type, format_name, suffix in (
                ("Foto.jpg", "image/jpeg", "JPEG", ".jpg"),
                ("Scan.png", "image/png", "PNG", ".png"),
            ):
                with self.subTest(filename=filename):
                    result = storage.store(
                        _image_upload(filename=filename, content_type=content_type, format_name=format_name),
                        owner_id=owner_id,
                        item_id=uuid.uuid4(),
                    )
                    path = storage.resolve_path(result.file_key)
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.suffix, suffix)
                    self.assertEqual((result.width, result.height), (48, 32))
                    self.assertTrue(Path(directory) in path.parents)

    def test_rejects_mismatched_extension_mime_type_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = DossierImageStorage(storage_path=directory, upload_max_bytes=1024 * 1024)
            with self.assertRaises(BadRequestError):
                storage.store(
                    _image_upload(filename="Foto.png", content_type="image/png", format_name="JPEG"),
                    owner_id=uuid.uuid4(),
                    item_id=uuid.uuid4(),
                )


if __name__ == "__main__":
    unittest.main()
