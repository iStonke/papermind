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
    PhoneScanJobStatusResponse,
    PhoneScanSessionCreateResponse,
    PhoneScanStatusResponse,
    PhoneScanUploadResponse,
)
from app.services.docscan_opencv import run_document_scan_pipeline
from app.services.import_staging import ImportStagingService
from app.services.scan_jobs import add_recent_file, ensure_job, fail_job, get_job, upsert_job

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


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _center_crop_bbox(width: int, height: int, ratio: float = 0.85) -> tuple[int, int, int, int]:
    crop_ratio = _clamp_float(ratio, 0.6, 0.95)
    target_w = max(40, int(round(width * crop_ratio)))
    target_h = max(40, int(round(height * crop_ratio)))
    left = max(0, (width - target_w) // 2)
    top = max(0, (height - target_h) // 2)
    right = min(width, left + target_w)
    bottom = min(height, top + target_h)
    return left, top, right, bottom


def _bbox_to_quad(left: int, top: int, right: int, bottom: int) -> "np.ndarray":
    return np.array(
        [
            [float(left), float(top)],
            [float(right - 1), float(top)],
            [float(right - 1), float(bottom - 1)],
            [float(left), float(bottom - 1)],
        ],
        dtype=np.float32,
    )


def _adaptive_canny(gray: "np.ndarray") -> "np.ndarray":
    median = float(np.median(gray))
    lower = int(_clamp_float(0.66 * median, 20, 220))
    upper = int(_clamp_float(1.33 * median, lower + 20, 255))
    return cv2.Canny(gray, lower, upper)


def _order_points(points: "np.ndarray") -> "np.ndarray":
    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]
    tl = points[np.argmin(sums)]
    br = points[np.argmax(sums)]
    tr = points[np.argmax(diffs)]
    bl = points[np.argmin(diffs)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _quad_angles_score(quad: "np.ndarray") -> float:
    def angle(a: "np.ndarray", b: "np.ndarray", c: "np.ndarray") -> float:
        ba = a - b
        bc = c - b
        denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))
        if denom <= 1e-6:
            return 0.0
        cosine = _clamp_float(float(np.dot(ba, bc)) / denom, -1.0, 1.0)
        return float(np.degrees(np.arccos(cosine)))

    tl, tr, br, bl = quad
    angles = [
        angle(bl, tl, tr),
        angle(tl, tr, br),
        angle(tr, br, bl),
        angle(br, bl, tl),
    ]
    mean_deviation = float(np.mean([abs(item - 90.0) for item in angles]))
    return _clamp_float(1.0 - (mean_deviation / 25.0), 0.0, 1.0)


def _quad_aspect_ratio(quad: "np.ndarray") -> float:
    tl, tr, br, bl = quad
    width = (float(np.linalg.norm(tr - tl)) + float(np.linalg.norm(br - bl))) / 2.0
    height = (float(np.linalg.norm(bl - tl)) + float(np.linalg.norm(br - tr))) / 2.0
    if height <= 1e-6:
        return 0.0
    return width / height


def _select_quad_candidate(contours: list["np.ndarray"], image_area: float) -> tuple["np.ndarray | None", bool]:
    best_score = -1.0
    best_quad: "np.ndarray" | None = None
    largest_contour: "np.ndarray" | None = None
    largest_area = 0.0
    sorted_contours = sorted(contours, key=lambda item: abs(float(cv2.contourArea(item))), reverse=True)[:20]

    for contour in sorted_contours:
        area = abs(float(cv2.contourArea(contour)))
        if area > largest_area:
            largest_area = area
            largest_contour = contour
        if area <= 0:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 1e-6:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue

        quad = _order_points(approx.reshape(4, 2).astype(np.float32))
        x, y, width, height = cv2.boundingRect(approx)
        bounding_area = float(max(1, width * height))
        rectangularity = area / bounding_area
        area_ratio = area / float(max(1.0, image_area))
        aspect_ratio = _quad_aspect_ratio(quad)
        angle_score = _quad_angles_score(quad)

        if area_ratio < 0.2 or area_ratio > 0.98:
            continue
        if rectangularity < 0.7:
            continue
        if aspect_ratio < 0.6 or aspect_ratio > 1.7:
            continue

        area_score = _clamp_float((area_ratio - 0.2) / 0.55, 0.0, 1.0)
        rect_score = _clamp_float((rectangularity - 0.7) / 0.25, 0.0, 1.0)
        aspect_center = 1.0
        aspect_score = _clamp_float(1.0 - abs(aspect_ratio - aspect_center) / 0.7, 0.0, 1.0)
        score = 0.4 * area_score + 0.25 * rect_score + 0.25 * angle_score + 0.1 * aspect_score
        if score > best_score:
            best_score = score
            best_quad = quad

    if best_quad is not None:
        return best_quad, False

    if largest_contour is not None and largest_area / float(max(1.0, image_area)) >= 0.08:
        rect = cv2.minAreaRect(largest_contour)
        box = cv2.boxPoints(rect)
        box_area = abs(float(cv2.contourArea(box.astype(np.float32))))
        box_ratio = box_area / float(max(1.0, image_area))
        if 0.1 <= box_ratio <= 0.98:
            return _order_points(box.astype(np.float32)), True

    return None, True


def _draw_debug_quad(image_rgb: "np.ndarray", quad: "np.ndarray") -> Image.Image:
    debug = image_rgb.copy()
    pts = quad.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(debug, [pts], True, (50, 230, 90), 4)
    for point in quad.astype(np.int32):
        cv2.circle(debug, (int(point[0]), int(point[1])), 7, (255, 80, 80), -1)
    return Image.fromarray(debug, mode="RGB")


def _try_warp_with_opencv(image: Image.Image) -> tuple[Image.Image, bool, Image.Image | None]:
    if not OPENCV_AVAILABLE:
        left, top, right, bottom = _center_crop_bbox(image.width, image.height, ratio=0.85)
        cropped = image.crop((left, top, right, bottom))
        return cropped, True, None

    original_rgb = np.array(image.convert("RGB"))  # type: ignore[arg-type]
    analysis_img, scale = _downscale_for_analysis(image, long_edge=1200)
    analysis_rgb = np.array(analysis_img.convert("RGB"))  # type: ignore[arg-type]
    gray = cv2.cvtColor(analysis_rgb, cv2.COLOR_RGB2GRAY)
    denoised = cv2.bilateralFilter(gray, 9, 55, 55)
    edges = _adaptive_canny(denoised)
    close_kernel = np.ones((5, 5), dtype=np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )
    thresh = cv2.bitwise_not(thresh)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    combined = cv2.bitwise_or(edges, thresh)
    contours, _ = cv2.findContours(combined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(max(1, analysis_rgb.shape[0] * analysis_rgb.shape[1]))
    quad_analysis, used_fallback = _select_quad_candidate(contours, image_area)

    if quad_analysis is None:
        left, top, right, bottom = _center_crop_bbox(analysis_rgb.shape[1], analysis_rgb.shape[0], ratio=0.85)
        quad_analysis = _bbox_to_quad(left, top, right, bottom)
        used_fallback = True

    inv_scale = 1.0 / max(scale, 1e-9)
    quad_original = quad_analysis * inv_scale
    quad_original[:, 0] = np.clip(quad_original[:, 0], 0, original_rgb.shape[1] - 1)
    quad_original[:, 1] = np.clip(quad_original[:, 1], 0, original_rgb.shape[0] - 1)
    quad_original = _order_points(quad_original.astype(np.float32))
    quad_area = abs(float(cv2.contourArea(quad_original)))
    frame_area = float(max(1, original_rgb.shape[0] * original_rgb.shape[1]))
    if quad_area / frame_area > 0.985:
        left, top, right, bottom = _center_crop_bbox(original_rgb.shape[1], original_rgb.shape[0], ratio=0.85)
        quad_original = _bbox_to_quad(left, top, right, bottom)
        used_fallback = True

    tl, tr, br, bl = quad_original
    width_a = float(np.linalg.norm(br - bl))
    width_b = float(np.linalg.norm(tr - tl))
    height_a = float(np.linalg.norm(tr - br))
    height_b = float(np.linalg.norm(tl - bl))
    max_width = max(32, int(round(max(width_a, width_b))))
    max_height = max(32, int(round(max(height_a, height_b))))

    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(quad_original, destination)
    warped = cv2.warpPerspective(original_rgb, matrix, (max_width, max_height))
    debug_overlay = _draw_debug_quad(original_rgb, quad_original)
    return Image.fromarray(warped, mode="RGB"), used_fallback, debug_overlay


def _crop_border_cleanup(image: Image.Image) -> Image.Image:
    if OPENCV_AVAILABLE:
        rgb = np.array(image.convert("RGB"))  # type: ignore[arg-type]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        threshold_floor = int(_clamp_float(np.percentile(blur, 55), 80, 220))
        bright_mask = cv2.inRange(blur, threshold_floor, 255)
        kernel = np.ones((7, 7), dtype=np.uint8)
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total_area = float(max(1, rgb.shape[0] * rgb.shape[1]))

        best_bbox: tuple[int, int, int, int] | None = None
        best_area = 0.0
        for contour in contours:
            area = abs(float(cv2.contourArea(contour)))
            if area <= best_area:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if width < 24 or height < 24:
                continue
            area_ratio = area / total_area
            if area_ratio < 0.35:
                continue
            best_area = area
            best_bbox = (x, y, x + width, y + height)

        if best_bbox:
            left, top, right, bottom = best_bbox
            inset = max(2, min(20, int(round(min(right - left, bottom - top) * 0.01))))
            left = min(max(0, left + inset), image.width - 1)
            top = min(max(0, top + inset), image.height - 1)
            right = max(left + 1, min(image.width, right - inset))
            bottom = max(top + 1, min(image.height, bottom - inset))
            return image.crop((left, top, right, bottom))

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    mask = gray.point(lambda value: 255 if value > 32 else 0)
    bbox = mask.getbbox()
    if not bbox:
        left, top, right, bottom = _center_crop_bbox(image.width, image.height, ratio=0.92)
        return image.crop((left, top, right, bottom))
    left, top, right, bottom = bbox
    inset = max(2, min(20, int(round(min(right - left, bottom - top) * 0.01))))
    left = min(max(0, left + inset), image.width - 1)
    top = min(max(0, top + inset), image.height - 1)
    right = max(left + 1, min(image.width, right - inset))
    bottom = max(top + 1, min(image.height, bottom - inset))
    return image.crop((left, top, right, bottom))


def _apply_clean_scan_filter(image: Image.Image) -> Image.Image:
    if OPENCV_AVAILABLE:
        rgb = np.array(image.convert("RGB"))  # type: ignore[arg-type]
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.8, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        p5 = float(np.percentile(l_channel, 5))
        p98 = float(np.percentile(l_channel, 98))
        if p98 - p5 < 20:
            p98 = p5 + 20
        l_stretch = np.clip((l_channel.astype(np.float32) - p5) * (255.0 / (p98 - p5)), 0, 255).astype(np.uint8)

        background = cv2.GaussianBlur(l_stretch, (0, 0), 25)
        bg_mean = float(np.mean(background))
        shadow_lift = np.clip(l_stretch.astype(np.float32) + (bg_mean - background.astype(np.float32)) * 0.65, 0, 255).astype(np.uint8)
        shadow_lift[shadow_lift > 245] = 255

        merged = cv2.merge((shadow_lift, a_channel, b_channel))
        rgb_balanced = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
        sharp = cv2.GaussianBlur(rgb_balanced, (0, 0), 1.1)
        out = cv2.addWeighted(rgb_balanced, 1.22, sharp, -0.22, 0)
        return Image.fromarray(out, mode="RGB")

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


def _is_scan_debug_enabled() -> bool:
    raw = str(os.getenv("VITE_WEBSCAN_DEBUG") or os.getenv("PHONE_SCAN_DEBUG") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _optimize_page(
    image: Image.Image,
    *,
    filter_mode: Literal["clean", "bw"] = "clean",
) -> tuple[Image.Image, bool, Image.Image | None]:
    warped, used_fallback, debug_overlay = _try_warp_with_opencv(image)
    cleaned = _crop_border_cleanup(warped)
    if filter_mode == "bw":
        filtered = _apply_bw_scan_filter(cleaned)
    else:
        filtered = _apply_clean_scan_filter(cleaned)
    final_page = _resize_for_pdf(filtered, long_edge=2200)
    return final_page, used_fallback, debug_overlay


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
    progress_callback: Callable[[str, str, float, int, int], None] | None = None,
) -> tuple[PhoneScanUploadedFileEntry, bool]:
    def report(state: str, step: str, progress: float, pages_done: int, pages_total: int) -> None:
        if progress_callback:
            progress_callback(state, step, progress, pages_done, pages_total)

    pages_total = max(0, len(job.raw_paths))
    report("receiving", "convert", 0.1, 0, pages_total)
    processed_pages: list[Image.Image] = []
    used_fallback_any = False
    proc_dir = _scan_proc_dir(job.session_id)
    proc_dir.mkdir(parents=True, exist_ok=True)
    debug_enabled = _is_scan_debug_enabled()

    for index, raw_path in enumerate(job.raw_paths, start=1):
        pages_done_before = max(0, index - 1)
        report(
            "processing",
            "detect",
            max(0.1, 0.1 + 0.7 * (pages_done_before / max(1, pages_total))),
            pages_done_before,
            pages_total,
        )
        image = _load_image(raw_path)
        report(
            "processing",
            "warp",
            max(0.12, 0.1 + 0.7 * (pages_done_before / max(1, pages_total))),
            pages_done_before,
            pages_total,
        )
        scan_result = run_document_scan_pipeline(image)
        optimized = scan_result.image
        used_fallback = not scan_result.used_warp
        used_fallback_any = used_fallback_any or used_fallback
        report(
            "processing",
            "clean",
            max(0.14, 0.1 + 0.7 * (index / max(1, pages_total))),
            index,
            pages_total,
        )
        processed_pages.append(optimized)
        if debug_enabled:
            debug_path = proc_dir / f"{index:03d}_debug_quad_overlay.jpg"
            optimized.save(debug_path, format="JPEG", quality=82, optimize=True)
        out_name = f"{index:03d}.jpg"
        out_path = proc_dir / out_name
        optimized.save(out_path, format="JPEG", quality=84, optimize=True)

    report("processing", "pdf", 0.9, pages_total, pages_total)
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
            session.step = "convert"
            session.progress = 0
            return copy.deepcopy(session)

    def mark_job_queued(self, token: str, *, job_id: str, filenames: list[str], client_info: dict[str, str]) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.latest_job_id = job_id
            session.pending_jobs += 1
            session.state = "receiving"
            session.step = "convert"
            session.progress = 10
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
            session.step = "pdf"
            session.progress = 100
            session.error_message = None
            if len(session.files) >= session.max_files:
                session.state = "closed"

    def mark_error(self, token: str, *, message: str) -> None:
        with self._lock:
            session = self._get_by_token_locked(token)
            session.pending_jobs = max(0, session.pending_jobs - 1)
            session.state = "error"
            session.step = "clean"
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
            external_latest_job_id = str(payload.get("latestJobId") or payload.get("latest_job_id") or "").strip()
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
            if external_latest_job_id:
                session.latest_job_id = external_latest_job_id
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
                fail_job(job.job_id, str(exc))
                try:
                    snapshot = _STORE.get_by_token(job.token)
                    _write_external_status(
                        job.session_id,
                        _build_external_status_payload(
                            session_id=job.session_id,
                            token=job.token,
                            state=snapshot.state,
                            step=snapshot.step or "clean",
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
        def on_progress(state: str, step: str, progress: float, pages_done: int, pages_total: int) -> None:
            _STORE.update_processing(job.token, step=step, progress=int(max(0.0, min(1.0, progress)) * 100))
            upsert_job(
                job.job_id,
                state="processing" if state == "processing" else "receiving",
                step=step,
                progress=progress,
                pages_total=pages_total,
                pages_done=pages_done,
                error=None,
            )

        uploaded_entry, used_fallback_any = process_phone_scan_job(
            job,
            progress_callback=on_progress,
        )
        _STORE.mark_ready(job.token, uploaded_entry=uploaded_entry)
        upsert_job(
            job.job_id,
            state="ready",
            step="pdf",
            progress=1.0,
            pages_total=max(1, len(job.raw_paths)),
            pages_done=max(1, len(job.raw_paths)),
            error=None,
        )
        try:
            snapshot = _STORE.get_by_token(job.token)
            _write_external_status(
                job.session_id,
                _build_external_status_payload(
                    session_id=job.session_id,
                    token=job.token,
                    state=snapshot.state,
                    step=snapshot.step or "pdf",
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
                    step="convert",
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
            latestJobId=session.latest_job_id,
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
        ensure_job(job_id, pages_total=len(raw_paths), session_id=session_id, token=normalized_token)
        upsert_job(
            job_id,
            session_id=session_id,
            token=normalized_token,
            state="receiving",
            step="convert",
            progress=0.0,
            pages_total=len(raw_paths),
            pages_done=0,
            error=None,
        )
        for original_name in original_names:
            add_recent_file(job_id, original_name)
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
                    step=snapshot.step or "convert",
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
        return PhoneScanUploadResponse(received=True, receivedCount=len(raw_paths), jobId=job_id)

    def get_job_status(self, *, job_id: str) -> PhoneScanJobStatusResponse:
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            raise BadRequestError("jobId is required")
        job = get_job(normalized_job_id)
        if not job:
            raise NotFoundError("Phone scan job not found")
        if job.session_id and job.token:
            external_status = _read_external_status(job.session_id)
            if external_status and str(external_status.get("token") or "").strip() == job.token:
                ext_job_id = str(external_status.get("latestJobId") or "").strip()
                if ext_job_id == normalized_job_id:
                    state = str(external_status.get("state") or "").strip().lower()
                    step = str(external_status.get("step") or "").strip().lower()
                    try:
                        progress = float(external_status.get("progress") or 0) / 100.0
                    except Exception:
                        progress = float(job.progress)
                    if state in {"receiving", "processing", "ready", "error"}:
                        mapped_state = state
                    else:
                        mapped_state = job.state
                    if step in {"convert", "detect", "warp", "clean", "pdf"}:
                        mapped_step = step
                    elif mapped_state in {"receiving"}:
                        mapped_step = "convert"
                    elif mapped_state in {"ready"}:
                        mapped_step = "pdf"
                    else:
                        mapped_step = job.step
                    pages_total = max(0, int(job.pages_total))
                    pages_done = int(job.pages_done)
                    if pages_total > 0:
                        if mapped_step in {"detect", "warp", "clean"}:
                            normalized = max(0.0, min(1.0, (progress - 0.1) / 0.7))
                            pages_done = max(0, min(pages_total, int(round(normalized * pages_total))))
                        elif mapped_step == "pdf" or mapped_state == "ready":
                            pages_done = pages_total
                        elif mapped_step == "convert":
                            pages_done = 0
                    upsert_job(
                        normalized_job_id,
                        state=mapped_state,
                        step=mapped_step,
                        progress=max(0.0, min(1.0, progress)),
                        pages_total=pages_total,
                        pages_done=pages_done,
                        error=str(external_status.get("errorMessage") or "").strip() or None,
                    )
                    job = get_job(normalized_job_id) or job
        return PhoneScanJobStatusResponse(
            jobId=job.job_id,
            state=job.state,
            step=job.step,
            progress=max(0.0, min(1.0, float(job.progress))),
            pagesTotal=max(0, int(job.pages_total)),
            pagesDone=max(0, int(job.pages_done)),
            recentFiles=list(job.recent_files[:3]),
            error=job.error,
            updatedAt=job.updated_at,
        )
