import copy
import io
import json
import logging
import os
import queue
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import quote_plus, urlsplit

from fastapi import Request, UploadFile
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError, StorageError
from app.db.session import SessionLocal
from app.schemas.phone_scan import (
    PhoneScanFileRead,
    PhoneScanSessionCreateResponse,
    PhoneScanStatusResponse,
    PhoneScanUploadResponse,
)
from app.services.import_staging import ImportStagingService

logger = logging.getLogger("papermind.phone_scan")
settings = get_settings()

HEIF_REGISTERED = False
SESSION_STATES = {"waiting", "receiving", "processing", "ready", "error", "expired", "closed"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/webp",
    "image/tiff",
    "image/bmp",
}

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    OPENCV_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    cv2 = None
    np = None
    OPENCV_AVAILABLE = False


@dataclass
class PhoneScanUploadedFileEntry:
    id: str
    filename: str
    size: int
    content_type: str
    created_at: datetime
    source_file_id: str
    page_count: int
    target_stage_id: str | None = None


@dataclass
class PhoneScanSessionRecord:
    id: str
    token: str
    created_at: datetime
    expires_at: datetime
    state: str
    max_files: int
    target_stage_id: str | None = None
    files: list[PhoneScanUploadedFileEntry] = field(default_factory=list)
    client_info: dict[str, str] = field(default_factory=dict)
    step: str | None = None
    progress: int = 0
    error_message: str | None = None
    latest_job_id: str | None = None
    latest_result_source_file_id: str | None = None
    pending_jobs: int = 0


@dataclass
class PhoneScanJob:
    session_id: str
    token: str
    job_id: str
    stage_id: str | None
    raw_paths: list[Path]
    original_names: list[str]
    content_types: list[str]
    source_ip: str
    source_ua: str
    filter_mode: Literal["clean", "bw"] = "clean"
    client_timestamps: list[str] = field(default_factory=list)


@dataclass
class PhoneScanUploadMetaItem:
    order: int
    client_timestamp: str
    filename: str


def _normalize_filename(filename: str, fallback: str = "upload.bin") -> str:
    raw = os.path.basename(str(filename or "").strip())
    if not raw:
        raw = fallback
    normalized = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return normalized or fallback


def _safe_scan_pdf_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    return f"Scan - {stamp}.pdf"


def _resolve_public_base_url(request: Request) -> str:
    configured = str(settings.public_web_base_url or "").strip()
    if configured:
        return configured.rstrip("/")

    origin = str(request.headers.get("origin") or "").strip()
    if origin and origin.lower() != "null":
        parts = urlsplit(origin)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}".rstrip("/")

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def _read_upload_bytes(file: UploadFile) -> bytes:
    max_bytes = settings.upload_max_bytes
    file.file.seek(0)
    data = io.BytesIO()
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                "Uploaded file exceeds maximum allowed size",
                details={"max_bytes": max_bytes, "filename": file.filename},
            )
        data.write(chunk)
    file.file.seek(0)
    payload = data.getvalue()
    if not payload:
        raise BadRequestError("Uploaded file is empty", details={"filename": file.filename})
    return payload


def _parse_upload_meta(meta_raw: str | None, expected_count: int) -> tuple[Literal["clean", "bw"], list[PhoneScanUploadMetaItem]]:
    if not meta_raw:
        default = [
            PhoneScanUploadMetaItem(order=index, client_timestamp="", filename="")
            for index in range(max(0, int(expected_count)))
        ]
        return "clean", default

    try:
        payload = json.loads(str(meta_raw))
    except Exception as exc:
        raise BadRequestError("Upload meta is invalid JSON") from exc

    filter_mode = "clean"
    items_payload: list[Any] = []
    if isinstance(payload, list):
        items_payload = payload
    elif isinstance(payload, dict):
        filter_mode = _normalize_filter_mode(str(payload.get("filterMode") or "clean"))
        if isinstance(payload.get("items"), list):
            items_payload = payload.get("items") or []
    else:
        raise BadRequestError("Upload meta has unsupported format")

    if not items_payload:
        default = [
            PhoneScanUploadMetaItem(order=index, client_timestamp="", filename="")
            for index in range(max(0, int(expected_count)))
        ]
        return filter_mode, default

    normalized: list[PhoneScanUploadMetaItem] = []
    for index, item in enumerate(items_payload):
        if not isinstance(item, dict):
            normalized.append(PhoneScanUploadMetaItem(order=index, client_timestamp="", filename=""))
            continue
        raw_order = item.get("order")
        try:
            order = int(raw_order)
        except Exception:
            order = index
        normalized.append(
            PhoneScanUploadMetaItem(
                order=max(0, order),
                client_timestamp=str(item.get("clientTimestamp") or "").strip()[:64],
                filename=_normalize_filename(str(item.get("filename") or "").strip(), fallback=f"photo-{index + 1}.jpg"),
            )
        )

    if len(normalized) < expected_count:
        for idx in range(len(normalized), expected_count):
            normalized.append(PhoneScanUploadMetaItem(order=idx, client_timestamp="", filename=""))
    elif len(normalized) > expected_count:
        normalized = normalized[:expected_count]
    return filter_mode, normalized


def _classify_image_upload(filename: str, content_type: str) -> None:
    ext = Path(filename).suffix.lower()
    normalized_type = content_type.strip().lower()
    if normalized_type in ALLOWED_IMAGE_CONTENT_TYPES:
        return
    if normalized_type.startswith("image/"):
        return
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return
    raise BadRequestError(
        "Unsupported file format. Only images are allowed for phone scan.",
        details={"filename": filename, "content_type": content_type},
    )


def _scan_raw_dir(session_id: str) -> Path:
    return (Path(settings.storage_path).resolve() / "scan_raw" / session_id).resolve()


def _scan_proc_dir(session_id: str) -> Path:
    return (Path(settings.storage_path).resolve() / "scan_proc" / session_id).resolve()


def _scan_pdf_dir(session_id: str) -> Path:
    return (Path(settings.storage_path).resolve() / "scan_pdf" / session_id).resolve()


def _scan_jobs_root() -> Path:
    return (Path(settings.storage_path).resolve() / "scan_jobs").resolve()


def _scan_job_queue_dir() -> Path:
    return (_scan_jobs_root() / "queued").resolve()


def _scan_job_processing_dir() -> Path:
    return (_scan_jobs_root() / "processing").resolve()


def _scan_job_done_dir() -> Path:
    return (_scan_jobs_root() / "done").resolve()


def _scan_job_failed_dir() -> Path:
    return (_scan_jobs_root() / "failed").resolve()


def _scan_job_status_dir() -> Path:
    return (_scan_jobs_root() / "status").resolve()


def _scan_job_status_path(session_id: str) -> Path:
    safe_session = re.sub(r"[^A-Za-z0-9_-]+", "", str(session_id or "").strip()) or "unknown"
    return (_scan_job_status_dir() / f"{safe_session}.json").resolve()


def _scan_worker_heartbeat_path() -> Path:
    return (_scan_jobs_root() / "worker-heartbeat.json").resolve()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp-{uuid.uuid4().hex}")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
        os.replace(temp_path, path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise StorageError("Failed to write phone scan metadata", details=str(exc)) from exc


def _read_json_safe(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _normalize_filter_mode(raw_value: str | None) -> Literal["clean", "bw"]:
    value = str(raw_value or "").strip().lower()
    if value in {"bw", "blackwhite", "black_white", "black-and-white", "binary"}:
        return "bw"
    return "clean"


def _has_fresh_worker_heartbeat() -> bool:
    payload = _read_json_safe(_scan_worker_heartbeat_path())
    if not payload:
        return False
    ts_raw = str(payload.get("timestamp") or "").strip()
    if not ts_raw:
        return False
    try:
        heartbeat_ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = datetime.now(timezone.utc) - heartbeat_ts
    return age.total_seconds() <= max(5, int(settings.phone_scan_worker_heartbeat_ttl_seconds))


def _should_use_external_worker() -> bool:
    mode = str(settings.phone_scan_worker_mode or "auto").strip().lower()
    if mode == "inline":
        return False
    if mode == "external":
        return True
    return _has_fresh_worker_heartbeat()


def _store_raw_upload(*, session_id: str, filename: str, payload: bytes) -> Path:
    target_dir = _scan_raw_dir(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_name = _normalize_filename(filename, fallback="photo.jpg")
    target_path = target_dir / f"{timestamp}_{safe_name}"
    temp_path = target_path.with_suffix(f"{target_path.suffix}.uploading")

    try:
        with temp_path.open("wb") as handle:
            handle.write(payload)
        os.replace(temp_path, target_path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise StorageError("Failed to persist phone scan upload", details=str(exc)) from exc
    return target_path


def _try_register_heif() -> None:
    global HEIF_REGISTERED
    if HEIF_REGISTERED:
        return
    try:
        from pillow_heif import register_heif_opener  # type: ignore

        register_heif_opener()
        HEIF_REGISTERED = True
    except Exception:
        HEIF_REGISTERED = True


def _load_image(path: Path) -> Image.Image:
    _try_register_heif()
    try:
        with Image.open(path) as raw:
            image = ImageOps.exif_transpose(raw)
            return image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise BadRequestError("Image data is invalid or unsupported", details={"path": str(path)}) from exc
    except OSError as exc:
        raise BadRequestError("Could not process uploaded image", details={"path": str(path), "error": str(exc)}) from exc


def _downscale_for_analysis(image: Image.Image, long_edge: int = 1200) -> tuple[Image.Image, float]:
    max_edge = max(image.width, image.height)
    if max_edge <= long_edge:
        return image.copy(), 1.0
    scale = long_edge / float(max_edge)
    width = max(1, int(round(image.width * scale)))
    height = max(1, int(round(image.height * scale)))
    return image.resize((width, height), resample=Image.Resampling.LANCZOS), scale


def _detect_document_bbox_fallback(image: Image.Image) -> tuple[int, int, int, int] | None:
    analysis, scale = _downscale_for_analysis(image, long_edge=1200)
    gray = ImageOps.grayscale(analysis)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    mask = edges.point(lambda value: 255 if value > 36 else 0)
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MedianFilter(3))
    bbox = mask.getbbox()
    if not bbox:
        return None

    left, top, right, bottom = bbox
    width = max(1, right - left)
    height = max(1, bottom - top)
    area_ratio = (width * height) / float(max(1, analysis.width * analysis.height))
    if area_ratio < 0.2:
        return None

    # Expand slightly to avoid clipping document edges.
    pad_x = int(round(width * 0.03))
    pad_y = int(round(height * 0.03))
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(analysis.width, right + pad_x)
    bottom = min(analysis.height, bottom + pad_y)

    inv_scale = 1.0 / max(scale, 1e-9)
    return (
        int(round(left * inv_scale)),
        int(round(top * inv_scale)),
        int(round(right * inv_scale)),
        int(round(bottom * inv_scale)),
    )


def _order_points(points: "np.ndarray") -> "np.ndarray":
    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]
    tl = points[np.argmin(sums)]
    br = points[np.argmax(sums)]
    tr = points[np.argmax(diffs)]
    bl = points[np.argmin(diffs)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _try_warp_with_opencv(image: Image.Image) -> tuple[Image.Image, bool]:
    if not OPENCV_AVAILABLE:
        return image, False

    rgb = image.convert("RGB")
    arr = np.array(rgb)  # type: ignore[arg-type]
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 75, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = arr.shape[0] * arr.shape[1]

    best_quad = None
    best_area = 0.0
    for contour in contours:
        area = abs(float(cv2.contourArea(contour)))
        if area < frame_area * 0.2 or area <= best_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4:
            continue
        points = approx.reshape(4, 2).astype(np.float32)
        ordered = _order_points(points)
        best_quad = ordered
        best_area = area

    if best_quad is None:
        return image, False

    tl, tr, br, bl = best_quad
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = int(max(width_a, width_b))
    max_height = int(max(height_a, height_b))
    if max_width < 20 or max_height < 20:
        return image, False

    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(best_quad, destination)
    warped = cv2.warpPerspective(arr, matrix, (max_width, max_height))
    return Image.fromarray(warped, mode="RGB"), True


def _crop_border_cleanup(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    contrast = ImageOps.autocontrast(gray, cutoff=1)
    inverted = ImageOps.invert(contrast)
    mask = inverted.point(lambda value: 255 if value > 12 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return image

    left, top, right, bottom = bbox
    width = max(1, right - left)
    height = max(1, bottom - top)
    area_ratio = (width * height) / float(max(1, image.width * image.height))
    if area_ratio < 0.3:
        return image

    margin = max(2, int(round(min(width, height) * 0.01)))
    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(image.width, right + margin)
    bottom = min(image.height, bottom + margin)
    return image.crop((left, top, right, bottom))


def _apply_clean_scan_filter(image: Image.Image) -> Image.Image:
    if OPENCV_AVAILABLE:
        rgb = np.array(image.convert("RGB"))  # type: ignore[arg-type]
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        merged = cv2.merge((l_channel, a_channel, b_channel))
        rgb_balanced = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)

        blurred = cv2.GaussianBlur(rgb_balanced, (0, 0), 1.0)
        sharpened = cv2.addWeighted(rgb_balanced, 1.2, blurred, -0.2, 0)
        gray = cv2.cvtColor(sharpened, cv2.COLOR_RGB2GRAY)
        boosted = np.clip(gray.astype(np.float32) * 1.06, 0, 255).astype(np.uint8)
        boosted[boosted > 245] = 255
        return Image.fromarray(cv2.cvtColor(boosted, cv2.COLOR_GRAY2RGB), mode="RGB")

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.MedianFilter(3))
    gray = ImageEnhance.Contrast(gray).enhance(1.38)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=125, threshold=3))
    gray = gray.point(lambda value: 255 if value > 245 else int(min(255, value * 1.06)))
    return gray.convert("RGB")


def _apply_bw_scan_filter(image: Image.Image) -> Image.Image:
    if OPENCV_AVAILABLE:
        gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)  # type: ignore[arg-type]
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        bw = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            12,
        )
        kernel = np.ones((2, 2), dtype=np.uint8)
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
        return Image.fromarray(cv2.cvtColor(bw, cv2.COLOR_GRAY2RGB), mode="RGB")

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.MedianFilter(3))
    bw = gray.point(lambda value: 255 if value > 170 else 0, mode="1")
    return bw.convert("RGB")


def _resize_for_pdf(image: Image.Image, long_edge: int = 2200) -> Image.Image:
    max_edge = max(image.width, image.height)
    if max_edge <= long_edge:
        return image
    scale = long_edge / float(max_edge)
    width = max(1, int(round(image.width * scale)))
    height = max(1, int(round(image.height * scale)))
    return image.resize((width, height), resample=Image.Resampling.LANCZOS)


def _optimize_page(image: Image.Image, *, filter_mode: Literal["clean", "bw"] = "clean") -> tuple[Image.Image, bool]:
    used_fallback = False

    warped, warped_ok = _try_warp_with_opencv(image)
    if not warped_ok:
        bbox = _detect_document_bbox_fallback(image)
        if bbox:
            left, top, right, bottom = bbox
            if right - left > 20 and bottom - top > 20:
                warped = image.crop((left, top, right, bottom))
            else:
                warped = image
                used_fallback = True
        else:
            warped = image
            used_fallback = True

    cleaned = _crop_border_cleanup(warped)
    if filter_mode == "bw":
        filtered = _apply_bw_scan_filter(cleaned)
    else:
        filtered = _apply_clean_scan_filter(cleaned)
    final_page = _resize_for_pdf(filtered, long_edge=2200)
    return final_page, used_fallback


def _build_pdf_bytes(images: list[Image.Image]) -> bytes:
    if not images:
        raise BadRequestError("No pages available for PDF creation")
    converted = [img.convert("RGB") for img in images]
    first, rest = converted[0], converted[1:]
    output = io.BytesIO()
    first.save(output, format="PDF", save_all=True, append_images=rest, resolution=200)
    data = output.getvalue()
    if not data.startswith(b"%PDF-"):
        raise StorageError("Failed to build phone scan PDF")
    return data


def _to_staging_source(*, db: Session, pdf_bytes: bytes, filename: str):
    staging_upload = UploadFile(filename=filename, file=io.BytesIO(pdf_bytes))
    service = ImportStagingService(db)
    try:
        result = service.upload_sources([staging_upload])
    finally:
        try:
            staging_upload.file.close()
        except Exception:
            pass
    if not result.items:
        raise StorageError("Failed to register phone scan output in import staging")
    return result.items[0]


def _file_read_from_entry(entry: PhoneScanUploadedFileEntry) -> PhoneScanFileRead:
    return PhoneScanFileRead(
        id=entry.id,
        filename=entry.filename,
        size=entry.size,
        contentType=entry.content_type,
        createdAt=entry.created_at,
        sourceFileId=entry.source_file_id,
        pageCount=entry.page_count,
        targetStageId=entry.target_stage_id,
    )


def _uploaded_entry_to_payload(entry: PhoneScanUploadedFileEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "filename": entry.filename,
        "size": int(entry.size),
        "contentType": entry.content_type,
        "createdAt": entry.created_at.isoformat(),
        "sourceFileId": entry.source_file_id,
        "pageCount": int(entry.page_count),
        "targetStageId": entry.target_stage_id,
    }


def _payload_to_uploaded_entry(payload: dict[str, Any]) -> PhoneScanUploadedFileEntry | None:
    try:
        entry_id = str(payload.get("id") or "").strip()
        filename = str(payload.get("filename") or "").strip()
        size = int(payload.get("size") or 0)
        content_type = str(payload.get("contentType") or payload.get("content_type") or "").strip() or "application/pdf"
        created_at_raw = str(payload.get("createdAt") or payload.get("created_at") or "").strip()
        source_file_id = str(payload.get("sourceFileId") or payload.get("source_file_id") or "").strip()
        page_count = int(payload.get("pageCount") or payload.get("page_count") or 0)
        target_stage_id = str(payload.get("targetStageId") or payload.get("target_stage_id") or "").strip() or None
        if not entry_id or not filename or size <= 0 or not source_file_id or page_count <= 0:
            return None
        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00")) if created_at_raw else datetime.now(timezone.utc)
        return PhoneScanUploadedFileEntry(
            id=entry_id,
            filename=filename,
            size=size,
            content_type=content_type,
            created_at=created_at,
            source_file_id=source_file_id,
            page_count=page_count,
            target_stage_id=target_stage_id,
        )
    except Exception:
        return None


def _read_external_status(session_id: str) -> dict[str, Any] | None:
    return _read_json_safe(_scan_job_status_path(session_id))


def _write_external_status(session_id: str, payload: dict[str, Any]) -> None:
    _write_json_atomic(_scan_job_status_path(session_id), payload)


def _build_external_status_payload(
    *,
    session_id: str,
    token: str,
    state: str,
    step: str,
    progress: int,
    error_message: str | None = None,
    files: list[PhoneScanUploadedFileEntry] | None = None,
    latest_job_id: str | None = None,
    latest_result_source_file_id: str | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "sessionId": session_id,
        "token": token,
        "state": state,
        "step": step,
        "progress": max(0, min(100, int(progress))),
        "errorMessage": (str(error_message or "").strip() or None),
        "latestJobId": latest_job_id,
        "latestResultSourceFileId": latest_result_source_file_id,
        "files": [_uploaded_entry_to_payload(entry) for entry in (files or [])],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _build_external_job_payload(job: PhoneScanJob) -> dict[str, Any]:
    return {
        "version": 1,
        "jobId": job.job_id,
        "sessionId": job.session_id,
        "token": job.token,
        "stageId": job.stage_id,
        "rawPaths": [str(path) for path in job.raw_paths],
        "originalNames": list(job.original_names),
        "contentTypes": list(job.content_types),
        "clientTimestamps": list(job.client_timestamps),
        "sourceIp": job.source_ip,
        "sourceUa": job.source_ua,
        "filterMode": job.filter_mode,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


def _queue_external_job(job: PhoneScanJob) -> Path:
    queue_dir = _scan_job_queue_dir()
    queue_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = (queue_dir / f"{job.job_id}.json").resolve()
    _write_json_atomic(manifest_path, _build_external_job_payload(job))
    return manifest_path


def process_phone_scan_job(
    job: PhoneScanJob,
    *,
    progress_callback: Callable[[str, int], None] | None = None,
) -> tuple[PhoneScanUploadedFileEntry, bool]:
    def report(step: str, progress: int) -> None:
        if progress_callback:
            progress_callback(step, progress)

    report("1/5: Konvertiere", 20)
    processed_pages: list[Image.Image] = []
    used_fallback_any = False
    proc_dir = _scan_proc_dir(job.session_id)
    proc_dir.mkdir(parents=True, exist_ok=True)

    for index, raw_path in enumerate(job.raw_paths, start=1):
        image = _load_image(raw_path)
        report(f"2/5: Erkenne Dokument ({index}/{len(job.raw_paths)})", 35)
        optimized, used_fallback = _optimize_page(image, filter_mode=job.filter_mode)
        used_fallback_any = used_fallback_any or used_fallback
        report(f"3/5: Begradige ({index}/{len(job.raw_paths)})", 55)
        report(f"4/5: Optimiere ({index}/{len(job.raw_paths)})", 75)
        processed_pages.append(optimized)
        out_name = f"{index:03d}.jpg"
        out_path = proc_dir / out_name
        optimized.save(out_path, format="JPEG", quality=84, optimize=True)

    report("5/5: Erzeuge PDF", 90)
    pdf_bytes = _build_pdf_bytes(processed_pages)
    pdf_dir = _scan_pdf_dir(job.session_id)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    final_pdf_path = pdf_dir / "scan.pdf"
    final_pdf_path.write_bytes(pdf_bytes)

    with SessionLocal() as db:
        source = _to_staging_source(db=db, pdf_bytes=pdf_bytes, filename=_safe_scan_pdf_filename())
        db.commit()

    uploaded_entry = PhoneScanUploadedFileEntry(
        id=str(uuid.uuid4()),
        filename=_safe_scan_pdf_filename(),
        size=len(pdf_bytes),
        content_type="application/pdf",
        created_at=datetime.now(timezone.utc),
        source_file_id=source.source_file_id,
        page_count=source.page_count,
        target_stage_id=job.stage_id,
    )
    return uploaded_entry, used_fallback_any


def _is_expired(session: PhoneScanSessionRecord, *, now: datetime | None = None) -> bool:
    check_time = now or datetime.now(timezone.utc)
    return check_time >= session.expires_at


class _InMemoryPhoneScanStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, PhoneScanSessionRecord] = {}
        self._token_to_session: dict[str, str] = {}

    def _cleanup_locked(self, now: datetime) -> None:
        purge_before = now - timedelta(hours=6)
        stale_ids: list[str] = []
        for session_id, session in self._sessions.items():
            if _is_expired(session, now=now):
                session.state = "expired"
            if session.expires_at < purge_before:
                stale_ids.append(session_id)
        for session_id in stale_ids:
            session = self._sessions.pop(session_id, None)
            if session:
                self._token_to_session.pop(session.token, None)

    def _normalize_max_files(self, requested_max_files: int | None) -> int:
        default_limit = max(1, int(settings.mobile_upload_default_max_files))
        hard_limit = max(1, int(settings.mobile_upload_max_files_limit))
        if requested_max_files is None:
            requested = default_limit
        else:
            requested = int(requested_max_files)
        return max(1, min(requested, hard_limit))

    def create_session(
        self,
        *,
        max_files: int | None,
        target_stage_id: str | None,
        client_info: dict[str, str],
    ) -> PhoneScanSessionRecord:
        now = datetime.now(timezone.utc)
        ttl = timedelta(minutes=settings.mobile_upload_session_ttl_minutes)
        session = PhoneScanSessionRecord(
            id=str(uuid.uuid4()),
            token=secrets.token_urlsafe(32),
            created_at=now,
            expires_at=now + ttl,
            state="waiting",
            max_files=self._normalize_max_files(max_files),
            target_stage_id=(str(target_stage_id or "").strip() or None),
            client_info=client_info or {},
        )
        with self._lock:
            self._cleanup_locked(now)
            self._sessions[session.id] = session
            self._token_to_session[session.token] = session.id
            return copy.deepcopy(session)

    def _get_by_token_locked(self, token: str) -> PhoneScanSessionRecord:
        session_id = self._token_to_session.get(token)
        if not session_id:
            raise NotFoundError("Phone scan session not found")
        session = self._sessions.get(session_id)
        if not session:
            raise NotFoundError("Phone scan session not found")
        if _is_expired(session):
            session.state = "expired"
        return session

    def get_by_token(self, token: str) -> PhoneScanSessionRecord:
        with self._lock:
            return copy.deepcopy(self._get_by_token_locked(token))

    def reserve_upload_slot(self, token: str) -> PhoneScanSessionRecord:
        with self._lock:
            session = self._get_by_token_locked(token)
            if session.state == "expired":
                raise BadRequestError("Upload session has expired")
            if session.state == "closed":
                raise BadRequestError("Upload session is already closed")
            remaining = max(0, session.max_files - (len(session.files) + session.pending_jobs))
            if remaining <= 0:
                session.state = "closed"
                raise BadRequestError(
                    "Upload limit reached for this session",
                    details={"remainingSlots": 0, "maxFiles": session.max_files},
                )
            session.state = "receiving"
            session.error_message = None
            session.step = "Empfange Fotos"
            session.progress = 5
            return copy.deepcopy(session)

    def mark_job_queued(self, token: str, *, job_id: str, filenames: list[str], client_info: dict[str, str]) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.latest_job_id = job_id
            session.pending_jobs += 1
            session.state = "receiving"
            session.step = "Upload empfangen"
            session.progress = 12
            if client_info:
                session.client_info.update({k: v for k, v in client_info.items() if v})
            if filenames:
                session.client_info["last_upload_names"] = ", ".join(filenames[:3])[:400]

    def update_processing(self, token: str, *, step: str, progress: int) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.state = "processing"
            session.step = step
            session.progress = max(0, min(100, int(progress)))

    def mark_ready(self, token: str, *, uploaded_entry: PhoneScanUploadedFileEntry) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.pending_jobs = max(0, session.pending_jobs - 1)
            session.files.append(uploaded_entry)
            session.latest_result_source_file_id = uploaded_entry.source_file_id
            session.state = "ready"
            session.step = "PDF bereit"
            session.progress = 100
            session.error_message = None
            if len(session.files) >= session.max_files:
                session.state = "closed"

    def mark_error(self, token: str, *, message: str) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.pending_jobs = max(0, session.pending_jobs - 1)
            session.state = "error"
            session.step = "Verarbeitung fehlgeschlagen"
            session.progress = 0
            session.error_message = str(message)[:500]

    def merge_external_status(self, token: str, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        with self._lock:
            session = self._get_by_token_locked(token)
            external_state = str(payload.get("state") or "").strip().lower()
            external_step = str(payload.get("step") or "").strip()
            external_error = str(payload.get("errorMessage") or "").strip()
            try:
                external_progress = int(payload.get("progress") or session.progress)
            except Exception:
                external_progress = session.progress

            if external_state in SESSION_STATES:
                session.state = external_state
                if external_state in {"ready", "closed", "error"}:
                    session.pending_jobs = 0
            if external_step:
                session.step = external_step
            session.progress = max(0, min(100, external_progress))
            session.error_message = external_error or None

            files_payload = payload.get("files")
            if isinstance(files_payload, list):
                known_source_ids = {entry.source_file_id for entry in session.files}
                for item in files_payload:
                    if not isinstance(item, dict):
                        continue
                    parsed = _payload_to_uploaded_entry(item)
                    if not parsed:
                        continue
                    if parsed.source_file_id in known_source_ids:
                        continue
                    session.files.append(parsed)
                    known_source_ids.add(parsed.source_file_id)
                    session.latest_result_source_file_id = parsed.source_file_id
                    session.pending_jobs = max(0, session.pending_jobs - 1)
                if len(session.files) >= session.max_files:
                    session.state = "closed"


_STORE = _InMemoryPhoneScanStore()


class _PhoneScanJobRunner:
    def __init__(self) -> None:
        self._queue: "queue.Queue[PhoneScanJob]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, name="phone-scan-jobs", daemon=True)
            self._thread.start()

    def enqueue(self, job: PhoneScanJob) -> None:
        self._ensure_started()
        self._queue.put(job)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._process_job(job)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("phone scan job failed session=%s job=%s err=%s", job.session_id, job.job_id, exc)
                _STORE.mark_error(job.token, message=str(exc))
                try:
                    snapshot = _STORE.get_by_token(job.token)
                    _write_external_status(
                        job.session_id,
                        _build_external_status_payload(
                            session_id=job.session_id,
                            token=job.token,
                            state=snapshot.state,
                            step=snapshot.step or "Verarbeitung fehlgeschlagen",
                            progress=snapshot.progress,
                            error_message=snapshot.error_message or str(exc),
                            files=snapshot.files,
                            latest_job_id=job.job_id,
                            latest_result_source_file_id=snapshot.latest_result_source_file_id,
                        ),
                    )
                except Exception:
                    logger.debug("inline phone scan error status sync failed session=%s job=%s", job.session_id, job.job_id)
            finally:
                self._queue.task_done()

    def _process_job(self, job: PhoneScanJob) -> None:
        uploaded_entry, used_fallback_any = process_phone_scan_job(
            job,
            progress_callback=lambda step, progress: _STORE.update_processing(job.token, step=step, progress=progress),
        )
        _STORE.mark_ready(job.token, uploaded_entry=uploaded_entry)
        try:
            snapshot = _STORE.get_by_token(job.token)
            _write_external_status(
                job.session_id,
                _build_external_status_payload(
                    session_id=job.session_id,
                    token=job.token,
                    state=snapshot.state,
                    step=snapshot.step or "PDF bereit",
                    progress=snapshot.progress,
                    error_message=snapshot.error_message,
                    files=snapshot.files,
                    latest_job_id=job.job_id,
                    latest_result_source_file_id=snapshot.latest_result_source_file_id,
                ),
            )
        except Exception:
            logger.debug("inline phone scan status sync failed session=%s job=%s", job.session_id, job.job_id)
        if used_fallback_any:
            logger.info("phone scan used fallback detection token=%s job=%s", job.token[:8], job.job_id)


_RUNNER = _PhoneScanJobRunner()


class PhoneScanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(
        self,
        *,
        request: Request,
        max_files: int | None = None,
        target_stage_id: str | None = None,
    ) -> PhoneScanSessionCreateResponse:
        session = _STORE.create_session(
            max_files=max_files,
            target_stage_id=target_stage_id,
            client_info={
                "ua": str(request.headers.get("user-agent") or "").strip()[:200],
                "ip": str(request.client.host if request.client else "").strip()[:128],
            },
        )
        base_url = _resolve_public_base_url(request)
        encoded_token = quote_plus(session.token)
        upload_url = f"{base_url}/m/scan?token={encoded_token}"
        status_url = f"{base_url}/api/phone-scan/status?token={encoded_token}"
        try:
            _write_external_status(
                session.id,
                _build_external_status_payload(
                    session_id=session.id,
                    token=session.token,
                    state="waiting",
                    step="Warte auf Upload…",
                    progress=0,
                    files=session.files,
                    latest_job_id=None,
                    latest_result_source_file_id=None,
                ),
            )
        except Exception:
            logger.debug("phone scan initial status write failed session=%s", session.id)
        return PhoneScanSessionCreateResponse(
            token=session.token,
            sessionId=session.id,
            expiresAt=session.expires_at,
            stageId=session.target_stage_id,
            uploadUrl=upload_url,
            statusUrl=status_url,
        )

    def get_status(self, *, token: str) -> PhoneScanStatusResponse:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise BadRequestError("Upload token is required")
        session = _STORE.get_by_token(normalized_token)
        external_status = _read_external_status(session.id)
        if external_status and str(external_status.get("token") or "").strip() == normalized_token:
            _STORE.merge_external_status(normalized_token, external_status)
            session = _STORE.get_by_token(normalized_token)

        files = [_file_read_from_entry(entry) for entry in session.files]
        last_three = [entry.filename for entry in sorted(session.files, key=lambda item: item.created_at, reverse=True)[:3]]
        return PhoneScanStatusResponse(
            state=session.state if session.state in SESSION_STATES else "error",
            step=session.step,
            progress=max(0, min(100, int(session.progress))),
            filesCount=len(files),
            files=files,
            last3Uploads=last_three,
            expiresAt=session.expires_at,
            maxFiles=session.max_files,
            stageId=session.target_stage_id,
            resultDocId=session.latest_result_source_file_id,
            errorMessage=session.error_message,
        )

    def upload_files(
        self,
        *,
        token: str,
        files: list[UploadFile],
        meta: str | None = None,
        request: Request | None = None,
    ) -> PhoneScanUploadResponse:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise BadRequestError("Upload token is required")
        if not files:
            raise BadRequestError("At least one file is required")

        existing_session = _STORE.get_by_token(normalized_token)
        external_status = _read_external_status(existing_session.id)
        if external_status and str(external_status.get("token") or "").strip() == normalized_token:
            _STORE.merge_external_status(normalized_token, external_status)

        session_snapshot = _STORE.reserve_upload_slot(normalized_token)
        session_id = session_snapshot.id
        filter_mode, meta_items = _parse_upload_meta(meta, len(files))

        indexed_uploads: list[tuple[int, int, UploadFile, PhoneScanUploadMetaItem]] = []
        for index, upload in enumerate(files):
            item_meta = meta_items[index] if index < len(meta_items) else PhoneScanUploadMetaItem(order=index, client_timestamp="", filename="")
            indexed_uploads.append((item_meta.order, index, upload, item_meta))
        indexed_uploads.sort(key=lambda entry: (entry[0], entry[1]))

        raw_paths: list[Path] = []
        original_names: list[str] = []
        content_types: list[str] = []
        client_timestamps: list[str] = []
        for _sort_order, index, upload, item_meta in indexed_uploads:
            fallback_name = item_meta.filename or f"photo-{index + 1}.jpg"
            original_name = _normalize_filename(upload.filename or fallback_name, fallback=fallback_name)
            content_type = str(upload.content_type or "").strip().lower()
            _classify_image_upload(original_name, content_type)
            payload = _read_upload_bytes(upload)
            raw_path = _store_raw_upload(session_id=session_id, filename=original_name, payload=payload)
            raw_paths.append(raw_path)
            original_names.append(original_name)
            content_types.append(content_type or "image/*")
            client_timestamps.append(item_meta.client_timestamp)

        job_id = str(uuid.uuid4())
        _STORE.mark_job_queued(
            normalized_token,
            job_id=job_id,
            filenames=original_names,
            client_info={
                "ua": str(request.headers.get("user-agent") or "").strip()[:200] if request else "",
                "ip": str(request.client.host if request and request.client else "").strip()[:128],
                "client_ts": next((ts for ts in client_timestamps if ts), ""),
            },
        )
        job = PhoneScanJob(
            session_id=session_id,
            token=normalized_token,
            job_id=job_id,
            stage_id=session_snapshot.target_stage_id,
            raw_paths=raw_paths,
            original_names=original_names,
            content_types=content_types,
            source_ip=str(request.client.host if request and request.client else "").strip()[:128],
            source_ua=str(request.headers.get("user-agent") or "").strip()[:200] if request else "",
            filter_mode=filter_mode,
            client_timestamps=client_timestamps,
        )
        try:
            snapshot = _STORE.get_by_token(normalized_token)
            _write_external_status(
                session_id,
                _build_external_status_payload(
                    session_id=session_id,
                    token=normalized_token,
                    state=snapshot.state,
                    step=snapshot.step or "Upload empfangen",
                    progress=snapshot.progress,
                    error_message=snapshot.error_message,
                    files=snapshot.files,
                    latest_job_id=job_id,
                    latest_result_source_file_id=snapshot.latest_result_source_file_id,
                ),
            )
        except Exception:
            logger.debug("phone scan status write failed session=%s job=%s", session_id, job_id)

        external_enqueued = False
        if _should_use_external_worker():
            try:
                _queue_external_job(job)
                external_enqueued = True
            except Exception as exc:
                logger.warning("phone scan external queue enqueue failed job=%s fallback=inline err=%s", job_id, exc)

        if not external_enqueued:
            _RUNNER.enqueue(job)
        return PhoneScanUploadResponse(received=len(raw_paths), jobId=job_id)
