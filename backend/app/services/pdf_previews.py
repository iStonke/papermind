"""Small PDF render helpers used only in bounded subprocesses."""
import math
import os
import uuid
import tempfile
from contextlib import closing
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


def _render_page(page, max_long_edge):
    width, height = float(page.get_width()), float(page.get_height())
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("Invalid PDF page dimensions")
    edge = min(1400, max(1, int(max_long_edge)))
    with closing(page.render(scale=min(4.0, edge / max(width, height)))) as bitmap:
        image = bitmap.to_pil().copy()
    image.thumbnail((edge, edge))
    return image


def page_image(path: Path, page_index: int, max_long_edge: int, mode: str):
    with closing(pdfium.PdfDocument(str(path))) as document:
        if page_index < 0 or page_index >= len(document):
            raise ValueError("Invalid page index")
        with closing(document[page_index]) as page:
            image = _render_page(page, max_long_edge)
    if mode == "bw":
        return _binarize_pil_image(image)
    return image.convert("L" if mode == "grayscale" else "RGB")


def color_pages(path: Path, max_long_edge: int):
    result = []
    with closing(pdfium.PdfDocument(str(path))) as document:
        for index in range(len(document)):
            with closing(document[index]) as page:
                image = _render_page(page, min(240, max_long_edge)).convert("RGB")
            colored = sum(1 for red, green, blue in image.getdata() if max(red, green, blue) - min(red, green, blue) >= 16)
            if colored >= max(12, int(image.width * image.height * 0.001)):
                result.append(index)
    return result


def png_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def convert_pdf(path, output, *, dpi_target, max_pixels, mode):
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.converting")
    try:
        with closing(pdfium.PdfDocument(str(path))) as document, tempfile.TemporaryDirectory() as directory:
            if not len(document):
                raise ValueError("PDF contains no pages")
            for index in range(len(document)):
                with closing(document[index]) as page:
                    width, height = page.get_size()
                    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                        raise ValueError("Invalid PDF page dimensions")
                    scale = min(max(1.0, dpi_target / 72), math.sqrt(max_pixels / (width * height)))
                    with closing(page.render(scale=scale)) as bitmap:
                        image = _binarize_pil_image(bitmap.to_pil()) if mode == "bw" else bitmap.to_pil().convert("L")
                page_path = Path(directory) / f"{index}.pdf"
                image.save(page_path, format="PDF", resolution=scale * 72)
                image.close()
                writer.add_page(PdfReader(str(page_path)).pages[0])
            writer.write(str(temporary))
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return str(output)


def _otsu_threshold(histogram: list[int]) -> int:
    """Optimaler globaler Schwellwert nach Otsu, direkt aus dem 256-Bin-
    Graustufen-Histogramm – reine Python-Arithmetik, ohne numpy."""
    total = sum(histogram)
    if total <= 0:
        return 128
    sum_all = sum(index * count for index, count in enumerate(histogram))
    weight_bg = 0
    sum_bg = 0.0
    best_variance = -1.0
    threshold = 128
    for level in range(256):
        weight_bg += histogram[level]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += level * histogram[level]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between > best_variance:
            best_variance = between
            threshold = level
    return threshold


def _binarize_pil_image(image: Image.Image) -> Image.Image:
    """Schwarz/Weiß per Otsu-Schwellwert – ohne cv2/numpy.

    Für den manuellen bw-Override, der auf der (bei aktiver Bereinigung bereits
    licht-korrigierten) Staging-Seite arbeitet. Die aufwändige Schatten-/
    Beleuchtungsglättung übernimmt weiterhin die Scan-Bereinigung im Worker;
    hier genügt eine saubere Binarisierung des bereits gleichmäßigen Bildes.
    """
    gray = image.convert("L")
    threshold = _otsu_threshold(gray.histogram())
    mono = gray.point(lambda value, cut=threshold: 255 if value > cut else 0)
    return mono.convert("1", dither=Image.Dither.NONE)
