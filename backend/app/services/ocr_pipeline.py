import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageOps
from pypdf import PdfReader

_NON_ALNUM_PATTERN = re.compile(r"[^A-Za-z0-9ÄÖÜäöüß\s.,;:!?%€@+\-_/()|]")
_NUMERIC_TOKEN_PATTERN = re.compile(r"\d")
_TABLE_NUMBER_PATTERN = re.compile(r"\d+[.,]?\d*")


def _normalize_line(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _postprocess_hyphenation(text_value: str) -> str:
    return re.sub(r"([A-Za-zÄÖÜäöüß])-\s*\n\s*([A-Za-zÄÖÜäöüß])", r"\1\2", text_value)


def _normalize_whitespace(text_value: str) -> str:
    value = str(text_value or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _extract_pdf_text_per_page(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    page_texts: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text_value = str(page.extract_text() or "").strip()
        page_texts.append((index, text_value))
    return page_texts


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
        str(language or "deu"),
    ]
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


def _preprocess_image(image: Image.Image, *, denoise: bool) -> Image.Image:
    processed = image.convert("L")
    processed = ImageOps.autocontrast(processed)
    if denoise:
        processed = processed.filter(ImageFilter.MedianFilter(size=3))
    processed = processed.point(lambda value: 0 if value < 145 else 255, mode="1")
    return processed.convert("L")


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
        row = {headers[i]: parts[i] for i in range(len(headers))}
        rows.append(row)
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
            language or "deu",
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
                "tokens": ordered,
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

    blocks = []
    if enable_layout:
        blocks = [
            {
                "text": entry["text"],
                "confidence": round(float(entry["confidence"] or 0.0) / 100.0, 3)
                if entry.get("confidence") is not None
                else None,
                "bbox": entry["bbox"],
            }
            for entry in line_entries
        ]

    avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else None
    return {
        "text": "\n".join(text_lines).strip(),
        "table_text": "\n".join(table_lines).strip(),
        "confidence": avg_conf,
        "blocks": blocks,
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


def _build_quality_metrics(full_text: str, page_confidences: list[float | None], warnings: list[str]) -> dict[str, Any]:
    normalized = str(full_text or "")
    char_count_total = len(normalized)
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9.,%€/-]+", normalized)
    numeric_tokens = [token for token in tokens if _NUMERIC_TOKEN_PATTERN.search(token)]
    percent_numeric_tokens = round((len(numeric_tokens) / max(1, len(tokens))) * 100.0, 2)

    valid_confidences = [value for value in page_confidences if isinstance(value, float)]
    avg_confidence = round(sum(valid_confidences) / len(valid_confidences), 3) if valid_confidences else None

    if char_count_total < 200:
        warnings.append("very_low_text")
    garbled_ratio = len(_NON_ALNUM_PATTERN.findall(normalized)) / max(1, len(normalized))
    if garbled_ratio > 0.14:
        warnings.append("many_garbled_chars")

    return {
        "avg_confidence": avg_confidence,
        "char_count_total": char_count_total,
        "percent_numeric_tokens": percent_numeric_tokens,
        "warnings": sorted(set(warnings)),
    }


def run_ocr_pipeline(
    original_path: Path,
    ocr_path: Path,
    runtime_settings: dict[str, Any],
    *,
    timeout_seconds: float,
    debug_preprocessed: bool = False,
) -> dict[str, Any]:
    ocr_settings = runtime_settings.get("ocr", {}) if isinstance(runtime_settings, dict) else {}
    requested_engine = str(ocr_settings.get("engine") or "tesseract").strip().lower()
    language = str(ocr_settings.get("language") or "deu").strip().lower() or "deu"
    dpi_target = int(ocr_settings.get("dpi_target") or 300)
    deskew = bool(ocr_settings.get("deskew", True))
    denoise = bool(ocr_settings.get("denoise", True))
    enable_layout = bool(ocr_settings.get("enable_layout", True))
    enable_table_detection = bool(ocr_settings.get("enable_table_detection", True))
    enable_hyphenation = bool(ocr_settings.get("postprocess_hyphenation", True))
    remove_headers_footers = bool(ocr_settings.get("remove_headers_footers", True))

    warnings: list[str] = []
    engine_used = requested_engine
    if requested_engine in {"paddleocr", "easyocr", "abbyy"}:
        warnings.append(f"engine_{requested_engine}_fallback_to_tesseract")
        engine_used = "tesseract"

    try:
        _run_ocrmypdf(
            original_path,
            ocr_path,
            language=language,
            deskew=deskew,
            denoise=denoise,
            dpi_target=dpi_target,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        warnings.append("ocrmypdf_failed_fallback_copy")
        warnings.append(str(exc))
        ocr_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original_path, ocr_path)

    source_for_text = ocr_path if ocr_path.exists() else original_path
    pdf_page_texts = _extract_pdf_text_per_page(source_for_text)
    pdf_doc = pdfium.PdfDocument(str(source_for_text))

    pages: list[dict[str, Any]] = []
    page_confidences: list[float | None] = []
    combined_table_chunks: list[dict[str, Any]] = []
    for index in range(len(pdf_doc)):
        page_no = index + 1
        page = pdf_doc[index]
        bitmap = page.render(scale=max(1.0, float(dpi_target) / 72.0))
        image = bitmap.to_pil()
        processed = _preprocess_image(image, denoise=denoise)

        if debug_preprocessed:
            debug_path = ocr_path.parent / f"debug-preprocessed-{page_no}.png"
            processed.save(debug_path)

        tesseract_data = _extract_tesseract_page_data(
            processed,
            language=language,
            dpi_target=dpi_target,
            enable_layout=enable_layout,
            enable_table_detection=enable_table_detection,
        )
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

    return {
        "engine_requested": requested_engine,
        "engine_used": engine_used,
        "text": full_text,
        "pages": pages,
        "tables": combined_table_chunks,
        "quality": quality,
    }
