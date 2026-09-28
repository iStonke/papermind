"""Run scan cleanup outside the long-lived worker process.

PDFium and OpenCV are isolated here so a native-library deadlock can be killed
by the parent timeout without blocking every subsequent scanner cleanup.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.ocr_pipeline import build_cleaned_scan_pdf


def _write_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--mode", choices=("white", "bw"), required=True)
    parser.add_argument("--dpi", type=int, required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)
    result_path = Path(args.result)
    crop_results: list[dict[str, object]] = []
    try:
        produced = build_cleaned_scan_pdf(
            source_path,
            output_path,
            mode=args.mode,
            dpi_target=max(72, args.dpi),
            crop_results=crop_results,
        )
        available = produced is not None and output_path.exists()
        _write_result(
            result_path,
            {
                "produced": available,
                "crop_results": crop_results,
                "message": "" if available else "cleanup_unavailable",
            },
        )
        return 0 if available else 2
    except Exception as exc:  # noqa: BLE001 - parent reports a safe fallback
        output_path.unlink(missing_ok=True)
        _write_result(
            result_path,
            {"produced": False, "crop_results": crop_results, "message": str(exc)[:300]},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
