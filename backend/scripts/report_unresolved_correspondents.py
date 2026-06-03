#!/usr/bin/env python
"""Report documents that still have no canonical correspondent."""

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
    parser = argparse.ArgumentParser(description="Report documents without document.correspondent_id.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of unresolved documents to list.")
    parser.add_argument("--include-deleted", action="store_true", help="Also include documents in trash.")
    parser.add_argument("--excerpt-chars", type=int, default=700, help="Maximum text excerpt characters per document.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation. Use 0 for compact output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.excerpt_chars < 0:
        raise SystemExit("--excerpt-chars must be >= 0")

    with SessionLocal() as db:
        report = CorrespondentBackfillService(db).unresolved_report(
            limit=args.limit,
            include_deleted=args.include_deleted,
            excerpt_chars=args.excerpt_chars,
        )

    if args.format == "markdown":
        print(report.to_markdown(), end="")
        return 0

    indent = None if args.indent == 0 else args.indent
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
