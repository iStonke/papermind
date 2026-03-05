from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    OPENCV_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None
    OPENCV_AVAILABLE = False


@dataclass
class DocScanResult:
    image: Image.Image
    used_warp: bool


def _order_quad(points: "np.ndarray") -> "np.ndarray":
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    top_left = points[np.argmin(sums)]
    bottom_right = points[np.argmax(sums)]
    top_right = points[np.argmin(diffs)]
    bottom_left = points[np.argmax(diffs)]
    return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)


def _find_document_quad(image_rgb: "np.ndarray") -> "np.ndarray | None":
    long_edge = max(image_rgb.shape[0], image_rgb.shape[1])
    scale = 1.0
    resized = image_rgb
    if long_edge > 1200:
        scale = 1200.0 / float(long_edge)
        resized = cv2.resize(
            image_rgb,
            (max(1, int(image_rgb.shape[1] * scale)), max(1, int(image_rgb.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 180)
    edges = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8), iterations=1)
    edges = cv2.erode(edges, np.ones((3, 3), dtype=np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    page_area = float(resized.shape[0] * resized.shape[1])
    best_quad: "np.ndarray | None" = None
    best_area = 0.0
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:40]:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 1e-5:
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4:
            continue
        area = abs(float(cv2.contourArea(approx)))
        if area < page_area * 0.2:
            continue
        if area > best_area:
            best_area = area
            best_quad = approx.reshape(4, 2).astype(np.float32)

    if best_quad is None:
        return None

    quad = _order_quad(best_quad)
    if scale != 1.0:
        quad = quad / max(scale, 1e-9)
    return quad


def _warp_document(image_rgb: "np.ndarray", quad: "np.ndarray") -> "np.ndarray":
    tl, tr, br, bl = quad
    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    target_w = max(16, int(round(max(width_top, width_bottom))))
    target_h = max(16, int(round(max(height_left, height_right))))

    destination = np.array(
        [[0, 0], [target_w - 1, 0], [target_w - 1, target_h - 1], [0, target_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(quad, destination)
    return cv2.warpPerspective(image_rgb, matrix, (target_w, target_h))


def _clean_scanned_document(image_rgb: "np.ndarray") -> "np.ndarray":
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    smooth_bg = cv2.GaussianBlur(normalized, (0, 0), 19)
    flattened = cv2.divide(normalized, smooth_bg, scale=255)
    denoised = cv2.fastNlMeansDenoising(flattened, None, 10, 7, 21)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), dtype=np.uint8), iterations=1)
    return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)


def run_document_scan_pipeline(image: Image.Image) -> DocScanResult:
    rgb_image = image.convert("RGB")
    if not OPENCV_AVAILABLE:
        return DocScanResult(image=rgb_image, used_warp=False)

    try:
        rgb = np.array(rgb_image)
        quad = _find_document_quad(rgb)
        if quad is None:
            return DocScanResult(image=rgb_image, used_warp=False)
        warped = _warp_document(rgb, quad)
        cleaned = _clean_scanned_document(warped)
        return DocScanResult(image=Image.fromarray(cleaned, mode="RGB"), used_warp=True)
    except Exception:
        return DocScanResult(image=rgb_image, used_warp=False)

