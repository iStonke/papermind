import logging
from io import BytesIO
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageOps
from pypdf import PdfReader, PdfWriter

try:  # Worker-only dependency; backend tests should still import this module without OpenCV.
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None

logger = logging.getLogger("papermind.ocr")

_NON_ALNUM_PATTERN = re.compile(r"[^A-Za-z0-9ÄÖÜäöüß\s.,;:!?%€@+\-_/()|]")
_NUMERIC_TOKEN_PATTERN = re.compile(r"\d")
_TABLE_NUMBER_PATTERN = re.compile(r"\d+[.,]?\d*")
_LANGUAGE_SEPARATOR_PATTERN = re.compile(r"[\s,+;]+")


class OCRPipelineError(RuntimeError):
    """Raised for corrupt, unreadable, or non-processable OCR inputs."""


@dataclass(frozen=True)
class OCRQuality:
    confidence_score: float | None
    status: str
    message: str


def _normalize_tesseract_languages(raw_language: str) -> str:
    parts = [part.strip().lower() for part in _LANGUAGE_SEPARATOR_PATTERN.split(str(raw_language or "")) if part.strip()]
    normalized = "+".join(dict.fromkeys(parts))
    return normalized or "deu+eng"


def _normalize_line(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _postprocess_hyphenation(text_value: str) -> str:
    return re.sub(r"([A-Za-zÄÖÜäöüß])-\s*\n\s*([A-Za-zÄÖÜäöüß])", r"\1\2", text_value)


def _normalize_whitespace(text_value: str) -> str:
    value = str(text_value or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = "\n".join(line.strip() for line in value.split("\n"))
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _validate_pdf_readable(pdf_path: Path) -> int:
    try:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
        page_count = len(pdf_doc)
    except Exception as exc:
        raise OCRPipelineError(f"PDF is corrupt or unreadable: {exc}") from exc

    if page_count <= 0:
        raise OCRPipelineError("PDF contains no readable pages")
    return page_count


def _extract_pdf_text_per_page(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        reader = PdfReader(str(pdf_path))
        page_texts: list[tuple[int, str]] = []
        for index, page in enumerate(reader.pages, start=1):
            text_value = str(page.extract_text() or "").strip()
            page_texts.append((index, text_value))
        return page_texts
    except Exception as exc:
        raise OCRPipelineError(f"PDF text extraction failed: {exc}") from exc


# CPU-Drosselung für die OCR (Pi-Härtung): begrenzt, wie viele Seiten ocrmypdf
# parallel verarbeitet. 0/leer = ocrmypdf-Default (alle Kerne). Auf dem Pi z. B.
# OCR_JOBS=3 setzen und im Container OMP_THREAD_LIMIT=1, damit OCR nicht alle
# Kerne auslastet (Hitze/Lüfter) und API/DB nicht aushungert.
OCR_JOBS = max(0, int(os.getenv("OCR_JOBS", "0") or "0"))


def _run_ocrmypdf(
    original_path: Path,
    ocr_path: Path,
    *,
    language: str,
    deskew: bool,
    denoise: bool,
    dpi_target: int,
    timeout_seconds: float,
) -> None:
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    if ocr_path.exists():
        ocr_path.unlink()

    command = [
        "ocrmypdf",
        "--force-ocr",
        "--rotate-pages",
        "--output-type",
        "pdf",
        "--oversample",
        str(int(dpi_target)),
        "-l",
        _normalize_tesseract_languages(language),
    ]
    if OCR_JOBS > 0:
        command.extend(["--jobs", str(OCR_JOBS)])
    if deskew:
        command.append("--deskew")
    if denoise:
        command.append("--clean")
    command.extend([str(original_path), str(ocr_path)])

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "ocrmypdf failed").strip()
        raise RuntimeError(f"OCR failed: {message}")
    if not ocr_path.exists() or not ocr_path.is_file():
        raise RuntimeError("OCR output file was not created")


SCAN_CLEANUP_MODES = ("off", "white", "bw")


def _normalize_scan_cleanup_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in SCAN_CLEANUP_MODES else "off"


def normalize_scan_cleanup_mode(value: Any) -> str:
    return _normalize_scan_cleanup_mode(value)


def _clean_scan_image(image: Image.Image, mode: str) -> Image.Image:
    """Glättet ungleichmäßige Beleuchtung und Faltenschatten, damit Scans einen
    richtig weißen Hintergrund bekommen.

    mode='white' erhält die Farben (Logos bleiben), zieht den Hintergrund aber
    auf Weiß. mode='bw' liefert einen sauberen Graustufen-Schwarz-auf-Weiß-Scan.

    Verfahren: pro Kanal wird der Hintergrund mit einem großen Gauß-Blur
    geschätzt und herausgeteilt. Das σ skaliert mit der Bildbreite, damit das
    Ergebnis auflösungsunabhängig ist.
    """
    if mode not in {"white", "bw"} or cv2 is None or np is None:
        return image

    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    width = rgb.shape[1]
    sigma = max(15.0, width / 48.0)  # ~35 @1700px, ~52 @2480px
    out = np.empty_like(rgb)
    for channel in range(3):
        plane = rgb[:, :, channel]
        background = cv2.GaussianBlur(plane, (0, 0), sigma)
        out[:, :, channel] = plane / np.maximum(background, 1.0) * 255.0
    out = np.clip(out, 0, 255)

    if mode == "white":
        # Sanfter Weißpunkt: der fast-weiße Hintergrund klippt auf reines Weiß.
        out = np.clip((out - 12.0) / (243.0 - 12.0) * 255.0, 0, 255)
        return Image.fromarray(out.astype(np.uint8), "RGB")

    # bw: Graustufen + Kontrast-Stretch → richtig weiß, sattes Schwarz.
    gray = cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)

    # Der Schwarzpunkt richtet sich nach der tatsächlichen Tinte der Seite.
    # Ein fester Wert passt nur zu sehr kräftigen Vorlagen; blasse Schrift bleibt
    # sonst grau, weil sie oberhalb der Schwelle landet und der Stretch sie sogar
    # noch aufhellt. Das Perzentil trifft die Strichkerne (Textdeckung einer
    # normalen Seite liegt deutlich darüber), die Grenzen fangen leere Seiten
    # und bildlastige Vorlagen ab.
    black_point = float(np.clip(np.percentile(gray, 2.0), 24.0, 150.0))
    white_point = 200.0
    if white_point - black_point < 60.0:
        white_point = black_point + 60.0

    gray = np.clip((gray - black_point) / (white_point - black_point) * 255.0, 0, 255)
    return Image.fromarray(gray.astype(np.uint8), "L")


def _build_cleaned_input_pdf(
    original_path: Path,
    output_path: Path,
    *,
    mode: str,
    dpi_target: int,
) -> Path | None:
    """Rendert jede Seite, bereinigt sie (siehe _clean_scan_image) und schreibt
    ein neues, reines Bild-PDF. Rückgabe ist der Ausgabepfad oder None, wenn die
    Bereinigung nicht möglich war (dann wird das Original weiterverwendet).

    Speicherschonend: Es wird immer nur eine Seite gleichzeitig als Einzelseiten-
    PDF gerendert und per PdfWriter angehängt (wichtig für große Scans auf dem Pi).
    """
    mode = _normalize_scan_cleanup_mode(mode)
    if mode not in {"white", "bw"} or cv2 is None or np is None:
        return None

    try:
        pdf_doc = pdfium.PdfDocument(str(original_path))
    except Exception as exc:  # noqa: BLE001 - Bereinigung ist optional
        logger.warning("scan cleanup: input unreadable, keeping original: %s", exc)
        return None

    page_count = len(pdf_doc)
    if page_count <= 0:
        return None

    scale = max(1.0, float(dpi_target) / 72.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            for index in range(page_count):
                page = pdf_doc[index]
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                cleaned = _clean_scan_image(image, mode)
                cleaned = cleaned.convert("L" if mode == "bw" else "RGB")
                page_pdf = Path(temp_dir) / f"page-{index}.pdf"
                cleaned.save(page_pdf, format="PDF", resolution=float(dpi_target))
                page_reader = PdfReader(str(page_pdf))
                writer.add_page(page_reader.pages[0])
            if len(writer.pages) <= 0:
                return None
            with output_path.open("wb") as handle:
                writer.write(handle)
    except Exception as exc:  # noqa: BLE001 - bei Fehler auf Original zurückfallen
        logger.warning("scan cleanup failed, keeping original: %s", exc)
        output_path.unlink(missing_ok=True)
        return None
    logger.info("scan cleanup done mode=%s pages=%s output=%s", mode, page_count, output_path)
    return output_path


def build_cleaned_scan_pdf(
    original_path: Path,
    output_path: Path,
    *,
    mode: str,
    dpi_target: int,
) -> Path | None:
    return _build_cleaned_input_pdf(
        original_path,
        output_path,
        mode=mode,
        dpi_target=dpi_target,
    )


def build_grayscale_pdf(
    original_path: Path,
    output_path: Path,
    *,
    dpi_target: int,
) -> Path | None:
    """Schreibt ein mehrseitiges Graustufen-PDF für den manuellen Importmodus."""
    try:
        pdf_doc = pdfium.PdfDocument(str(original_path))
    except Exception as exc:  # noqa: BLE001 - Import kann das Original weiterverwenden
        logger.warning("grayscale conversion: input unreadable: %s", exc)
        return None

    if len(pdf_doc) <= 0:
        return None

    scale = max(1.0, float(dpi_target) / 72.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            for index in range(len(pdf_doc)):
                image = pdf_doc[index].render(scale=scale).to_pil().convert("L")
                page_path = Path(temp_dir) / f"page-{index}.pdf"
                image.save(page_path, format="PDF", resolution=float(dpi_target))
                writer.add_page(PdfReader(str(page_path)).pages[0])
            with output_path.open("wb") as handle:
                writer.write(handle)
    except Exception as exc:  # noqa: BLE001 - der Aufrufer meldet den Importfehler
        logger.warning("grayscale conversion failed: %s", exc)
        output_path.unlink(missing_ok=True)
        return None
    return output_path


def detect_pdf_color_page_indices(pdf_path: Path, *, max_long_edge: int = 240) -> list[int] | None:
    """Ermittelt Seiten mit echten Farbpixeln, nicht nur RGB-kodierten Grautönen."""
    try:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 - fehlende Info lässt die UI Auswahl zu
        logger.warning("color detection: input unreadable: %s", exc)
        return None

    color_pages: list[int] = []
    for index in range(len(pdf_doc)):
        try:
            page = pdf_doc[index]
            long_edge_pt = max(float(page.get_width()), float(page.get_height())) or 1.0
            scale = max(0.1, min(2.0, float(max_long_edge) / long_edge_pt))
            image = page.render(scale=scale).to_pil().convert("RGB")
            # Kleine JPEG-Artefakte zählen nicht als Farbe. Ein farbiger Stempel,
            # ein Logo oder ein Foto überschreitet diese Schwelle klar.
            colored_pixels = sum(
                1
                for red, green, blue in image.getdata()
                if max(red, green, blue) - min(red, green, blue) >= 16
            )
            if colored_pixels >= max(12, int(image.width * image.height * 0.001)):
                color_pages.append(index)
        except Exception as exc:  # noqa: BLE001 - eine defekte Seite blockiert den Import nicht
            logger.warning("color detection failed page=%s: %s", index, exc)
    return color_pages


def render_pdf_page_color_preview(
    pdf_path: Path,
    *,
    page_index: int,
    mode: str,
    max_long_edge: int = 1400,
) -> bytes | None:
    """Rendert die tatsächlich zu importierende Farbvariante als PNG."""
    if mode not in {"auto", "color", "grayscale", "bw"}:
        return None
    try:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
        if page_index < 0 or page_index >= len(pdf_doc):
            return None
        page = pdf_doc[page_index]
        long_edge_pt = max(float(page.get_width()), float(page.get_height())) or 1.0
        scale = max(0.1, min(4.0, float(max_long_edge) / long_edge_pt))
        image = page.render(scale=scale).to_pil()
        if mode == "grayscale":
            image = image.convert("L")
        elif mode == "bw":
            image = _clean_scan_image(image, "bw")
        else:
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - die lokale Vorschau bleibt Fallback
        logger.warning("color preview render failed page=%s mode=%s: %s", page_index, mode, exc)
        return None


def render_pdf_page_preview(
    pdf_path: Path,
    output_path: Path,
    *,
    max_long_edge: int,
    page_index: int = 0,
) -> Path | None:
    """Rendert eine PDF-Seite als PNG-Vorschau.

    Wird nach der Scan-Bereinigung gebraucht: die vom Host gelieferte Vorschau
    zeigt noch den Rohscan und muss durch die bereinigte Seite ersetzt werden.
    """
    try:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 - Vorschau ist optional
        logger.warning("preview render: input unreadable: %s", exc)
        return None

    if len(pdf_doc) <= page_index:
        return None

    try:
        page = pdf_doc[page_index]
        long_edge_pt = max(float(page.get_width()), float(page.get_height())) or 1.0
        scale = max(0.1, min(4.0, float(max_long_edge) / long_edge_pt))
        image = page.render(scale=scale).to_pil()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.thumbnail((max_long_edge, max_long_edge))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG", optimize=True)
    except Exception as exc:  # noqa: BLE001 - Vorschau ist optional
        logger.warning("preview render failed path=%s err=%s", pdf_path, exc)
        output_path.unlink(missing_ok=True)
        return None
    return output_path


def _deskew_cv_image(gray_image: Any) -> Any:
    if cv2 is None or np is None:
        return gray_image

    inverted = cv2.bitwise_not(gray_image)
    coords = np.column_stack(np.where(inverted > 0))
    if coords.size == 0:
        return gray_image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.25 or abs(angle) > 15:
        return gray_image

    height, width = gray_image.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray_image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _run_unpaper_if_available(image: Image.Image) -> Image.Image:
    if shutil.which("unpaper") is None:
        return image

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "input.pgm"
        output_path = Path(temp_dir) / "output.pgm"
        image.convert("L").save(input_path, format="PPM")
        command = ["unpaper", "--no-noisefilter", str(input_path), str(output_path)]
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not output_path.exists():
            logger.warning("unpaper preprocessing skipped: %s", (result.stderr or result.stdout or "").strip())
            return image
        with Image.open(output_path) as cleaned:
            return cleaned.convert("L")


def _preprocess_image(image: Image.Image, *, deskew: bool, denoise: bool, use_unpaper: bool) -> Image.Image:
    logger.debug("ocr preprocessing start size=%s deskew=%s denoise=%s unpaper=%s", image.size, deskew, denoise, use_unpaper)
    if cv2 is not None and np is not None:
        gray = np.array(image.convert("L"))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        processed = clahe.apply(gray)
        if denoise:
            processed = cv2.fastNlMeansDenoising(processed, None, 10, 7, 21)
        if deskew:
            processed = _deskew_cv_image(processed)
        _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed = cv2.medianBlur(processed, 3) if denoise else processed
        output = Image.fromarray(processed).convert("L")
    else:
        output = image.convert("L")
        output = ImageOps.autocontrast(output)
        if denoise:
            output = output.filter(ImageFilter.MedianFilter(size=3))
        output = output.point(lambda value: 0 if value < 145 else 255, mode="1").convert("L")

    if use_unpaper:
        output = _run_unpaper_if_available(output)
    logger.debug("ocr preprocessing done size=%s", output.size)
    return output


def _parse_tsv_rows(tsv_text: str) -> list[dict[str, Any]]:
    lines = [line for line in str(tsv_text or "").splitlines() if line.strip()]
    if len(lines) <= 1:
        return []

    headers = lines[0].split("\t")
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < len(headers):
            continue
        rows.append({headers[i]: parts[i] for i in range(len(headers))})
    return rows


def _line_to_table_row(tokens: list[dict[str, Any]]) -> tuple[str, int]:
    if not tokens:
        return "", 0
    ordered = sorted(tokens, key=lambda token: int(token.get("left") or 0))
    columns: list[str] = []
    current_tokens: list[str] = []
    previous_right = None
    for token in ordered:
        text_value = str(token.get("text") or "").strip()
        if not text_value:
            continue
        left = int(token.get("left") or 0)
        width = int(token.get("width") or 0)
        right = left + width
        if previous_right is not None and (left - previous_right) >= 32:
            if current_tokens:
                columns.append(" ".join(current_tokens).strip())
            current_tokens = [text_value]
        else:
            current_tokens.append(text_value)
        previous_right = right

    if current_tokens:
        columns.append(" ".join(current_tokens).strip())

    clean_columns = [column for column in columns if column]
    if not clean_columns:
        return "", 0
    return " | ".join(clean_columns), len(clean_columns)


def _word_payload(token: dict[str, Any]) -> dict[str, Any]:
    conf = 0.0
    try:
        conf = float(token.get("conf") or 0.0)
    except (TypeError, ValueError):
        pass
    left = int(token.get("left") or 0)
    top = int(token.get("top") or 0)
    width = int(token.get("width") or 0)
    height = int(token.get("height") or 0)
    return {
        "text": str(token.get("text") or "").strip(),
        "confidence": round(conf / 100.0, 3),
        "bbox": [left, top, left + width, top + height],
        "block": int(token.get("block_num") or 0),
        "paragraph": int(token.get("par_num") or 0),
        "line": int(token.get("line_num") or 0),
    }


def _extract_tesseract_page_data(
    image: Image.Image,
    *,
    language: str,
    dpi_target: int,
    enable_layout: bool,
    enable_table_detection: bool,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        image_path = Path(temp_file.name)
        image.save(image_path, format="PNG")

    try:
        command = [
            "tesseract",
            str(image_path),
            "stdout",
            "-l",
            _normalize_tesseract_languages(language),
            "--dpi",
            str(int(dpi_target)),
            "--psm",
            "6",
            "tsv",
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "tesseract failed").strip()
            raise RuntimeError(message)
        rows = _parse_tsv_rows(result.stdout)
    finally:
        image_path.unlink(missing_ok=True)

    grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    confidences: list[float] = []
    words: list[dict[str, Any]] = []
    for row in rows:
        text_value = str(row.get("text") or "").strip()
        if not text_value:
            continue
        try:
            conf = float(row.get("conf") or -1)
        except (TypeError, ValueError):
            conf = -1
        if conf < 0:
            continue

        block_no = int(row.get("block_num") or 0)
        par_no = int(row.get("par_num") or 0)
        line_no = int(row.get("line_num") or 0)
        grouped[(block_no, par_no, line_no)].append(row)
        confidences.append(conf)
        words.append(_word_payload(row))

    line_entries: list[dict[str, Any]] = []
    for key in sorted(grouped.keys()):
        tokens = grouped[key]
        ordered = sorted(tokens, key=lambda token: int(token.get("left") or 0))
        line_text = _normalize_line(" ".join(str(token.get("text") or "") for token in ordered))
        if not line_text:
            continue
        token_conf = []
        for token in ordered:
            try:
                token_conf.append(float(token.get("conf") or -1))
            except (TypeError, ValueError):
                pass
        line_conf = sum(token_conf) / len(token_conf) if token_conf else None
        left = min(int(token.get("left") or 0) for token in ordered)
        top = min(int(token.get("top") or 0) for token in ordered)
        right = max(int(token.get("left") or 0) + int(token.get("width") or 0) for token in ordered)
        bottom = max(int(token.get("top") or 0) + int(token.get("height") or 0) for token in ordered)

        table_row = ""
        table_columns = 0
        if enable_table_detection:
            table_row, table_columns = _line_to_table_row(ordered)

        line_entries.append(
            {
                "text": line_text,
                "confidence": line_conf,
                "bbox": [left, top, right, bottom],
                "words": [_word_payload(token) for token in ordered if str(token.get("text") or "").strip()],
                "table_row": table_row,
                "table_columns": table_columns,
            }
        )

    text_lines = [entry["text"] for entry in line_entries]
    table_lines: list[str] = []
    if enable_table_detection:
        for entry in line_entries:
            table_row = str(entry.get("table_row") or "").strip()
            if not table_row:
                continue
            numeric_hits = len(_TABLE_NUMBER_PATTERN.findall(table_row))
            if entry.get("table_columns", 0) >= 3 or numeric_hits >= 2:
                table_lines.append(table_row)

    lines = [
        {
            "text": entry["text"],
            "confidence": round(float(entry["confidence"] or 0.0) / 100.0, 3)
            if entry.get("confidence") is not None
            else None,
            "bbox": entry["bbox"],
            "words": entry.get("words") or [],
        }
        for entry in line_entries
    ]

    blocks = []
    if enable_layout:
        blocks = [{"text": entry["text"], "confidence": entry["confidence"], "bbox": entry["bbox"]} for entry in lines]

    avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else None
    return {
        "text": "\n".join(text_lines).strip(),
        "table_text": "\n".join(table_lines).strip(),
        "confidence": avg_conf,
        "blocks": blocks,
        "lines": lines,
        "words": words,
    }


def _remove_repeated_headers_footers(page_texts: list[str], *, enabled: bool) -> list[str]:
    if not enabled or len(page_texts) < 3:
        return page_texts

    first_counter: Counter[str] = Counter()
    last_counter: Counter[str] = Counter()
    parsed_pages: list[tuple[list[str], str, str]] = []
    for text_value in page_texts:
        lines = [line.strip() for line in str(text_value or "").splitlines() if line.strip()]
        first = lines[0].lower() if lines else ""
        last = lines[-1].lower() if lines else ""
        parsed_pages.append((lines, first, last))
        if first:
            first_counter[first] += 1
        if last:
            last_counter[last] += 1

    threshold = max(2, int(len(page_texts) * 0.6))
    repeated_first = {line for line, count in first_counter.items() if count >= threshold and len(line) >= 4}
    repeated_last = {line for line, count in last_counter.items() if count >= threshold and len(line) >= 4}

    cleaned: list[str] = []
    for lines, first, last in parsed_pages:
        mutable = list(lines)
        if mutable and first in repeated_first:
            mutable = mutable[1:]
        if mutable and last in repeated_last:
            mutable = mutable[:-1]
        cleaned.append("\n".join(mutable).strip())
    return cleaned


def _normalize_numeric_tokens(text_value: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        return token.replace("O", "0").replace("o", "0")

    return re.sub(r"\b[0-9Oo][0-9Oo.,]+\b", replacer, text_value)


def _quality_from_confidence(confidence_score: float | None) -> OCRQuality:
    if confidence_score is None:
        return OCRQuality(None, "error", "OCR-Konfidenz konnte nicht berechnet werden. Manuelle Prüfung empfohlen.")
    if confidence_score >= 80.0:
        return OCRQuality(confidence_score, "good", "OCR-Qualität gut.")
    if confidence_score >= 60.0:
        return OCRQuality(confidence_score, "warning", "OCR-Qualität eingeschränkt. KI-Ergebnisse können unzuverlässig sein.")
    return OCRQuality(confidence_score, "error", "OCR-Qualität schlecht. Manuelle Prüfung empfohlen.")


def _build_quality_metrics(full_text: str, page_confidences: list[float | None], warnings: list[str]) -> dict[str, Any]:
    normalized = str(full_text or "")
    char_count_total = len(normalized)
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9.,%€/-]+", normalized)
    numeric_tokens = [token for token in tokens if _NUMERIC_TOKEN_PATTERN.search(token)]
    percent_numeric_tokens = round((len(numeric_tokens) / max(1, len(tokens))) * 100.0, 2)

    valid_confidences = [value for value in page_confidences if isinstance(value, float)]
    avg_confidence = round(sum(valid_confidences) / len(valid_confidences), 3) if valid_confidences else None
    confidence_score = round(avg_confidence * 100.0, 1) if avg_confidence is not None else None
    quality = _quality_from_confidence(confidence_score)

    if char_count_total < 200:
        warnings.append("very_low_text")
    garbled_ratio = len(_NON_ALNUM_PATTERN.findall(normalized)) / max(1, len(normalized))
    if garbled_ratio > 0.14:
        warnings.append("many_garbled_chars")
    if quality.status != "good":
        warnings.append(f"ocr_quality_{quality.status}")

    return {
        "avg_confidence": avg_confidence,
        "confidence_score": quality.confidence_score,
        "status": quality.status,
        "message": quality.message,
        "char_count_total": char_count_total,
        "percent_numeric_tokens": percent_numeric_tokens,
        "warnings": sorted(set(warnings)),
    }


def run_ocr_lite(
    pdf_path: Path,
    *,
    page_index: int = 0,
    language: str = "deu+eng",
    max_long_side_px: int = 2800,
    page_segmentation_mode: int = 6,
) -> str:
    """Lightweight single-page OCR for staging title suggestions.

    Skips ocrmypdf and NlMeans denoising entirely.
    Pipeline: pdfium render → CLAHE + Otsu binarization → Tesseract (text mode).
    Typical runtime: 2–6 s for a single A4 scan page.
    """
    if not pdf_path.exists() or not pdf_path.is_file():
        raise OCRPipelineError(f"PDF not found: {pdf_path}")

    try:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        raise OCRPipelineError(f"PDF unreadable: {exc}") from exc

    if len(pdf_doc) == 0:
        raise OCRPipelineError("PDF has no pages")

    page_index = min(max(0, page_index), len(pdf_doc) - 1)
    page = pdf_doc[page_index]

    # Determine render scale: target at most max_long_side_px on the longest side,
    # but always at least 150 DPI (scale = DPI/72).
    width_pt = page.get_width() or 595.0
    height_pt = page.get_height() or 842.0
    long_side_pt = max(width_pt, height_pt)
    scale_for_cap = max_long_side_px / long_side_pt          # keeps pixels ≤ cap
    scale_for_min_dpi = 150.0 / 72.0                         # floor: 150 DPI
    scale = max(scale_for_min_dpi, scale_for_cap)

    try:
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
    except Exception as exc:
        raise OCRPipelineError(f"pdfium render failed: {exc}") from exc

    # Lightweight preprocessing: CLAHE contrast enhancement + Otsu binarization.
    # No NlMeans (far too slow on large images), no unpaper.
    if cv2 is not None and np is not None:
        gray = np.array(image.convert("L"))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, binarized = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed = Image.fromarray(binarized).convert("L")
    else:
        processed = image.convert("L")
        processed = ImageOps.autocontrast(processed)
        processed = processed.point(lambda v: 0 if v < 145 else 255, mode="1").convert("L")

    dpi_hint = max(72, int(round(scale * 72)))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image_path = Path(tmp.name)
        processed.save(image_path, format="PNG")

    try:
        psm = int(page_segmentation_mode)
        if psm not in {3, 4, 6, 11, 12}:
            psm = 6
        result = subprocess.run(
            [
                "tesseract",
                str(image_path),
                "stdout",
                "-l", _normalize_tesseract_languages(language),
                "--dpi", str(dpi_hint),
                "--psm", str(psm),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "tesseract failed").strip())
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("tesseract timed out after 45 s")
    finally:
        image_path.unlink(missing_ok=True)


def run_ocr_pipeline(
    original_path: Path,
    ocr_path: Path,
    runtime_settings: dict[str, Any],
    *,
    timeout_seconds: float,
    debug_preprocessed: bool = False,
) -> dict[str, Any]:
    started_at = time.monotonic()
    if not original_path.exists() or not original_path.is_file():
        raise OCRPipelineError("Input PDF file does not exist")

    ocr_settings = runtime_settings.get("ocr", {}) if isinstance(runtime_settings, dict) else {}
    requested_engine = str(ocr_settings.get("engine") or "tesseract").strip().lower()
    language = _normalize_tesseract_languages(str(ocr_settings.get("language") or "deu+eng"))
    dpi_target = max(300, int(ocr_settings.get("dpi_target") or 300))
    deskew = bool(ocr_settings.get("deskew", True))
    denoise = bool(ocr_settings.get("denoise", True))
    use_unpaper = bool(ocr_settings.get("use_unpaper", True))
    enable_layout = bool(ocr_settings.get("enable_layout", True))
    enable_table_detection = bool(ocr_settings.get("enable_table_detection", True))
    enable_hyphenation = bool(ocr_settings.get("postprocess_hyphenation", True))
    remove_headers_footers = bool(ocr_settings.get("remove_headers_footers", True))
    scan_cleanup = _normalize_scan_cleanup_mode(ocr_settings.get("scan_cleanup"))
    page_count = _validate_pdf_readable(original_path)
    logger.info(
        "ocr pipeline start input=%s pages=%s lang=%s dpi=%s deskew=%s denoise=%s scan_cleanup=%s",
        original_path,
        page_count,
        language,
        dpi_target,
        deskew,
        denoise,
        scan_cleanup,
    )

    warnings: list[str] = []
    engine_used = requested_engine
    if requested_engine in {"paddleocr", "easyocr", "abbyy"}:
        warnings.append(f"engine_{requested_engine}_fallback_to_tesseract")
        engine_used = "tesseract"

    # Scan-Bereinigung: erzeugt vor dem OCR ein gereinigtes (weißes bzw. S/W)
    # Bild-PDF, das ocrmypdf dann mit der Textebene versieht. So bekommt die
    # angezeigte ocr.pdf einen richtig weißen Hintergrund ohne Faltenschatten.
    ocr_input_path = original_path
    cleaned_input_path: Path | None = None
    if scan_cleanup in {"white", "bw"}:
        candidate = ocr_path.parent / f"{ocr_path.stem}.cleaned-input.pdf"
        produced = _build_cleaned_input_pdf(
            original_path,
            candidate,
            mode=scan_cleanup,
            dpi_target=dpi_target,
        )
        if produced is not None:
            cleaned_input_path = produced
            ocr_input_path = produced
        else:
            warnings.append("scan_cleanup_failed")

    try:
        logger.info("ocr stage searchable_pdf start input=%s output=%s", ocr_input_path, ocr_path)
        _run_ocrmypdf(
            ocr_input_path,
            ocr_path,
            language=language,
            deskew=deskew,
            denoise=denoise,
            dpi_target=dpi_target,
            timeout_seconds=timeout_seconds,
        )
        logger.info("ocr stage searchable_pdf done output=%s", ocr_path)
    except Exception as exc:
        warnings.append("ocrmypdf_failed_fallback_copy")
        warnings.append(str(exc))
        logger.warning("ocrmypdf failed, falling back to input copy: %s", exc)
        ocr_path.parent.mkdir(parents=True, exist_ok=True)
        # Auch im Fehlerfall die bereinigte Variante behalten, damit die Anzeige weiß bleibt.
        shutil.copy2(ocr_input_path, ocr_path)
    finally:
        if cleaned_input_path is not None:
            cleaned_input_path.unlink(missing_ok=True)

    source_for_text = ocr_path if ocr_path.exists() else original_path
    pdf_page_texts = _extract_pdf_text_per_page(source_for_text)
    try:
        pdf_doc = pdfium.PdfDocument(str(source_for_text))
    except Exception as exc:
        raise OCRPipelineError(f"OCR PDF render failed: {exc}") from exc

    pages: list[dict[str, Any]] = []
    page_confidences: list[float | None] = []
    combined_table_chunks: list[dict[str, Any]] = []
    for index in range(len(pdf_doc)):
        page_no = index + 1
        logger.info("ocr stage page_render start page=%s dpi=%s", page_no, dpi_target)
        page = pdf_doc[index]
        bitmap = page.render(scale=max(1.0, float(dpi_target) / 72.0))
        image = bitmap.to_pil()
        processed = _preprocess_image(image, deskew=deskew, denoise=denoise, use_unpaper=use_unpaper)
        logger.info("ocr stage page_preprocess done page=%s", page_no)

        if debug_preprocessed:
            debug_path = ocr_path.parent / f"debug-preprocessed-{page_no}.png"
            processed.save(debug_path)

        logger.info("ocr stage tesseract start page=%s", page_no)
        tesseract_data = _extract_tesseract_page_data(
            processed,
            language=language,
            dpi_target=dpi_target,
            enable_layout=enable_layout,
            enable_table_detection=enable_table_detection,
        )
        logger.info("ocr stage tesseract done page=%s confidence=%s", page_no, tesseract_data.get("confidence"))
        extracted_pdf_text = ""
        if index < len(pdf_page_texts):
            extracted_pdf_text = str(pdf_page_texts[index][1] or "").strip()
        page_text = extracted_pdf_text or str(tesseract_data.get("text") or "").strip()
        table_text = str(tesseract_data.get("table_text") or "").strip()
        confidence = tesseract_data.get("confidence")
        page_confidences.append(confidence if isinstance(confidence, float) else None)

        pages.append(
            {
                "page": page_no,
                "text": page_text,
                "blocks": tesseract_data.get("blocks") or [],
                "lines": tesseract_data.get("lines") or [],
                "words": tesseract_data.get("words") or [],
                "confidence": confidence,
                "table_text": table_text,
            }
        )

        if table_text:
            combined_table_chunks.append({"page": page_no, "text": table_text})

    page_texts = [str(page.get("text") or "") for page in pages]
    page_texts = _remove_repeated_headers_footers(page_texts, enabled=remove_headers_footers)
    for idx, cleaned_text in enumerate(page_texts):
        text_value = cleaned_text
        if enable_hyphenation:
            text_value = _postprocess_hyphenation(text_value)
        text_value = _normalize_numeric_tokens(text_value)
        text_value = _normalize_whitespace(text_value)
        pages[idx]["text"] = text_value

    full_text = "\n\n".join([str(page.get("text") or "").strip() for page in pages if str(page.get("text") or "").strip()])
    quality = _build_quality_metrics(full_text, page_confidences, warnings)
    processing_time_seconds = round(time.monotonic() - started_at, 3)
    logger.info(
        "ocr pipeline done input=%s pages=%s seconds=%s confidence=%s status=%s",
        original_path,
        page_count,
        processing_time_seconds,
        quality.get("confidence_score"),
        quality.get("status"),
    )

    return {
        "engine_requested": requested_engine,
        "engine_used": engine_used,
        "text": full_text,
        "confidence_score": quality.get("confidence_score"),
        "quality_status": quality.get("status"),
        "page_count": page_count,
        "processing_time_seconds": processing_time_seconds,
        "pages": pages,
        "tables": combined_table_chunks,
        "quality": quality,
    }
