import unittest

from app.services.ocr_pipeline import (
    _binarize_pil_image,
    _build_quality_metrics,
    _clean_scan_image,
    _normalize_tesseract_languages,
    _otsu_threshold,
    _postprocess_hyphenation,
    build_bw_pdf,
    cv2,
    np,
)

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None


class OCRPipelineTest(unittest.TestCase):
    def test_language_normalization_defaults_to_german_and_english(self) -> None:
        self.assertEqual(_normalize_tesseract_languages(""), "deu+eng")
        self.assertEqual(_normalize_tesseract_languages("deu, eng deu"), "deu+eng")

    def test_hyphenation_postprocessing_joins_line_end_words(self) -> None:
        self.assertEqual(_postprocess_hyphenation("Ver-\narbeitung"), "Verarbeitung")

    def test_quality_thresholds(self) -> None:
        good = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.81], [])
        warning = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.79], [])
        error = _build_quality_metrics("Das ist ein lesbarer OCR Text mit ausreichend Inhalt.", [0.59], [])

        self.assertEqual(good["status"], "good")
        self.assertEqual(warning["status"], "warning")
        self.assertEqual(error["status"], "error")
        self.assertEqual(good["confidence_score"], 81.0)


@unittest.skipIf(cv2 is None or np is None or Image is None, "scan cleanup requires opencv/numpy (worker image)")
class ScanCleanupContrastTest(unittest.TestCase):
    """Die Bereinigung muss Text schwaerzen, nicht aufhellen."""

    WIDTH = 1240
    HEIGHT = 1754

    def _gradient(self, draw) -> None:
        # Beleuchtungsverlauf wie bei einem Flachbettscan.
        for x in range(self.WIDTH):
            shade = int(150 + 70 * (x / self.WIDTH))
            draw.line([(x, 0), (x, self.HEIGHT)], fill=(shade, shade, shade - 6))

    def _page(self, ink_level: int):
        page = Image.new("RGB", (self.WIDTH, self.HEIGHT))
        draw = ImageDraw.Draw(page)
        self._gradient(draw)
        # Duenne, kurze Striche als Textmodell. Flaechige Balken waeren
        # unrealistisch: sie ziehen den geschaetzten Hintergrund mit herunter
        # und verhalten sich wie ein Foto, nicht wie Schrift.
        for row in range(28):
            y = 200 + row * 48
            for word in range(9):
                x = 150 + word * 110
                # Tinte reflektiert anteilig weniger als das Papier daneben, ist
                # also immer dunkler als der lokale Untergrund - ein absoluter
                # Grauwert waere im hellen Bereich der Seite heller als das Papier.
                local_background = 150 + 70 * (x / self.WIDTH)
                effective = int(ink_level * local_background / 255)
                draw.rectangle([x, y, x + 78, y + 3], fill=(effective,) * 3)
        return page

    @staticmethod
    def _ink_level(image) -> float:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        return float(arr[arr <= np.percentile(arr, 3.0)].mean())

    @staticmethod
    def _background_level(image) -> float:
        arr = np.asarray(image.convert("L"), dtype=np.float32)
        return float(arr[arr >= np.percentile(arr, 90.0)].mean())

    def test_medium_ink_becomes_dark_instead_of_washed_out(self) -> None:
        # Mitteldunkle Tinte wurde vom festen Schwarzpunkt frueher aufgehellt.
        for ink_level in (80, 120, 160):
            with self.subTest(ink_level=ink_level):
                cleaned = _clean_scan_image(self._page(ink_level), "bw")
                self.assertLess(self._ink_level(cleaned), 60.0)
                self.assertGreater(self._background_level(cleaned), 250.0)

    def test_blank_page_stays_white(self) -> None:
        blank = Image.new("RGB", (self.WIDTH, self.HEIGHT))
        self._gradient(ImageDraw.Draw(blank))

        cleaned = _clean_scan_image(blank, "bw")

        arr = np.asarray(cleaned.convert("L"), dtype=np.float32)
        # Ohne Tinte darf der adaptive Schwarzpunkt kein Rauschen hervorholen.
        self.assertGreater(float(arr.mean()), 250.0)
        self.assertEqual(float((arr < 128).mean()), 0.0)


@unittest.skipIf(Image is None, "PIL erforderlich")
class ManualBwConversionTest(unittest.TestCase):
    """Der manuelle bw-Override läuft cv2-frei (PIL + Otsu), damit er auch im
    Backend-Prozess funktioniert – dort fehlt opencv."""

    def test_otsu_splits_between_two_peaks(self) -> None:
        histogram = [0] * 256
        histogram[30] = 500   # dunkle Tinte
        histogram[220] = 5000  # heller Hintergrund
        threshold = _otsu_threshold(histogram)
        self.assertTrue(30 <= threshold < 220, f"Schwellwert {threshold} liegt nicht zwischen den Moden")

    def test_binarize_yields_pure_black_and_white(self) -> None:
        # Grauverlauf → nach Binarisierung nur noch zwei Werte
        gradient = Image.new("L", (256, 32))
        gradient.putdata([x for _ in range(32) for x in range(256)])
        mono = _binarize_pil_image(gradient.convert("RGB"))
        levels = set(mono.convert("L").getdata())
        self.assertTrue(levels <= {0, 255}, f"nicht bitonal: {sorted(levels)}")
        self.assertEqual(len(levels), 2, "sollte sowohl Schwarz als auch Weiß enthalten")

    def test_build_bw_pdf_is_readable_and_bitonal(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.pdf"
            page = Image.new("RGB", (600, 800), (255, 255, 255))
            draw = ImageDraw.Draw(page)
            draw.rectangle([60, 80, 540, 130], fill=(190, 40, 40))   # Farbe
            draw.rectangle([60, 200, 400, 240], fill=(40, 40, 40))    # dunkler Text
            page.save(src, format="PDF", resolution=150.0)

            out = Path(tmp) / "bw.pdf"
            result = build_bw_pdf(src, out, dpi_target=200)
            self.assertIsNotNone(result)
            self.assertTrue(out.exists())

            import pypdfium2 as pdfium

            rendered = pdfium.PdfDocument(str(out))[0].render(scale=1.0).to_pil().convert("RGB")
            colored = sum(1 for r, g, b in rendered.getdata() if max(r, g, b) - min(r, g, b) >= 16)
            self.assertEqual(colored, 0, "bw-PDF darf keine Farbpixel enthalten")


if __name__ == "__main__":
    unittest.main()
