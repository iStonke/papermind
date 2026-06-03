#!/usr/bin/env python
"""Backfill canonical correspondents for existing documents.

Default is a dry run. Use ``--apply`` to write matches.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.services.correspondent_backfill import CorrespondentBackfillService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill document.correspondent_id from existing metadata/text.")
    parser.add_argument("--apply", action="store_true", help="Write matches. Without this flag, only report matches.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of documents without correspondent to scan.")
    parser.add_argument(
        "--min-score",
        type=int,
        default=500,
        help="Minimum match score to accept. 500 accepts alias contains; 1000+ accepts matchers/exact matches.",
    )
    parser.add_argument("--include-deleted", action="store_true", help="Also scan documents in trash.")
    parser.add_argument("--text-chars", type=int, default=6000, help="Maximum OCR/text characters per document.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation. Use 0 for compact output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.text_chars < 0:
        raise SystemExit("--text-chars must be >= 0")

    with SessionLocal() as db:
        result = CorrespondentBackfillService(db).run(
            limit=args.limit,
            dry_run=not args.apply,
            min_score=args.min_score,
            include_deleted=args.include_deleted,
            text_chars=args.text_chars,
        )

    indent = None if args.indent == 0 else args.indent
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
