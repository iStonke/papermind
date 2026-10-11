"""Bounded PDF processing outside the API process (also isolates PDFium)."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
import base64
from pathlib import Path

_slots = threading.BoundedSemaphore(1)


def run_pdf_task(operation: str, **arguments):
    from app.core.config import get_settings
    from app.core.errors import BadRequestError, StorageError
    settings = get_settings()
    timeout = settings.pdf_processing_timeout_seconds
    request = {"operation": operation, "arguments": arguments,
               "timeout": timeout, "memory_bytes": settings.pdf_processing_memory_mb * 1024 * 1024}
    if not _slots.acquire(timeout=timeout):
        raise StorageError("PDF processing is busy; please retry")
    try:
        try:
            result = subprocess.run([sys.executable, "-m", "app.services.pdf_tasks"],
                input=json.dumps(request), capture_output=True, text=True, timeout=timeout,
                # PDFium may import numpy. OpenBLAS's default thread stacks can
                # consume the entire address-space budget before a PDF opens.
                env={**{key: value for key, value in os.environ.items()
                       if key in {"PATH", "PYTHONPATH", "LANG", "LC_ALL", "TZ"}},
                     "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        except subprocess.TimeoutExpired as exc:
            raise StorageError("PDF processing exceeded its time limit") from exc
    finally:
        _slots.release()
    if result.returncode != 0:
        raise StorageError("PDF processing exceeded its resources or failed")
    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise StorageError("PDF processing returned an invalid result") from exc
    if payload.get("error") == "BAD_REQUEST":
        raise BadRequestError(payload["message"])
    if "error" in payload:
        raise StorageError("PDF processing failed")
    return payload["result"]


def main():
    request = json.loads(sys.stdin.read())
    if sys.platform.startswith("linux"):
        import resource
        memory = int(request["memory_bytes"])
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        cpu = max(1, math.ceil(request["timeout"]))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    from app.services.document_storage import DocumentStorageService
    from app.core.errors import BadRequestError
    args = request["arguments"]
    storage = DocumentStorageService(storage_path=args["storage_path"],
        upload_max_bytes=args.get("upload_max_bytes", 1), text_check_pages=args.get("text_check_pages", 2))
    try:
        if request["operation"] == "thumbnail":
            import uuid
            result = storage._create_thumbnail(uuid.UUID(args["document_id"]), Path(args["path"]), filename=args["filename"])
        elif request["operation"] == "quick_text":
            result = storage._extract_quick_text_sample(Path(args["path"]))
        elif request["operation"] == "reorder":
            result = storage._reorder_pdf_pages(Path(args["path"]), args["order"], destination=Path(args["destination"]))
        elif request["operation"] == "count":
            from pypdf import PdfReader
            try:
                result = len(PdfReader(args["path"]).pages)
            except Exception as exc:
                raise BadRequestError("PDF is corrupt or unreadable") from exc
        elif request["operation"] == "ocr_lite":
            from app.services.ocr_pipeline import _run_ocr_lite
            result = _run_ocr_lite(Path(args["path"]), page_index=args["page_index"],
                language=args["language"], max_long_side_px=args["max_long_side_px"],
                page_segmentation_mode=args["page_segmentation_mode"],
                timeout_seconds=max(1.0, request["timeout"] - 2.0))
        elif request["operation"] == "convert":
            from app.services.pdf_previews import convert_pdf
            result = convert_pdf(args["path"], args["output_path"], dpi_target=args["dpi_target"],
                                 max_pixels=args["max_pixels"], mode=args["mode"])
        elif request["operation"] in {"color_pages", "color_preview", "preview"}:
            from app.services.pdf_previews import color_pages, page_image, png_bytes
            if request["operation"] == "color_pages":
                result = color_pages(Path(args["path"]), args["max_long_edge"])
            else:
                image = page_image(Path(args["path"]), args["page_index"], args["max_long_edge"], args.get("mode", "auto"))
                if request["operation"] == "color_preview":
                    result = base64.b64encode(png_bytes(image)).decode("ascii")
                else:
                    output = Path(args["output_path"])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(png_bytes(image))
                    result = str(output)
        else:
            raise ValueError("Unknown PDF operation")
        print(json.dumps({"result": result}))
    except BadRequestError as exc:
        print(json.dumps({"error": "BAD_REQUEST", "message": exc.message}))
    except Exception:
        print(json.dumps({"error": "FAILED"}))


if __name__ == "__main__":
    main()
