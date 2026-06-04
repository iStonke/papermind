"""Mini-CLI für den Altbestand-Import (AP10 Schritt 9).

Trockenlauf (Default) – zeigt Zusammenfassung und schreibt optional einen
CSV-Report; mit ``--apply`` werden die PDFs importiert und Anzeigename,
Korrespondent und Sach-Tags gesetzt.

Beispiele:
    python -m app.cli.backlog_import --csv dateiliste.csv --dir /pfad/PDFs --report vorschau.csv
    python -m app.cli.backlog_import --csv dateiliste.csv --dir /pfad/PDFs --apply
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.services.backlog_import import BacklogImportService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Altbestand-Import (Trockenlauf/Anwenden)")
    parser.add_argument("--csv", required=True, help="CSV-Datei (Dateiname,Tags)")
    parser.add_argument("--dir", required=True, help="Ordner mit den PDF-Dateien")
    parser.add_argument("--apply", action="store_true", help="PDFs tatsächlich importieren (sonst nur Trockenlauf)")
    parser.add_argument("--limit", type=int, default=None, help="Nur die ersten N PDFs verarbeiten")
    parser.add_argument("--report", default=None, help="Pfad für den CSV-Report des Trockenlaufs")
    args = parser.parse_args(argv)

    with open(args.csv, encoding="utf-8") as handle:
        csv_content = handle.read()

    db = SessionLocal()
    try:
        service = BacklogImportService(db)
        if args.apply:
            result = service.apply(csv_content=csv_content, pdf_dir=args.dir, limit=args.limit)
            print("Import abgeschlossen:")
            print(f"  erstellt:            {result.created}")
            print(f"  mit Korrespondent:   {result.with_correspondent}")
            print(f"  übersprungen (da schon vorhanden): {result.skipped_existing}")
            print(f"  übersprungen (kein PDF):           {result.skipped_no_pdf}")
            print(f"  Fehler:              {len(result.errors)}")
            for filename, message in result.errors[:20]:
                print(f"    - {filename}: {message}")
            return 0

        plan = service.plan(csv_content=csv_content, pdf_dir=args.dir)
        print("Trockenlauf (es wurde NICHTS geschrieben):")
        print(f"  CSV-Zeilen:            {plan.total_rows}")
        print(f"  PDFs im Ordner:        {plan.pdfs_in_folder}")
        print(f"  PDF zugeordnet:        {plan.matched_pdf}")
        print(f"  PDF fehlt:             {len(plan.missing_pdf)}")
        print(f"  PDF ohne CSV-Zeile:    {len(plan.extra_pdf)}")
        print(f"  mit Korrespondent:     {plan.with_correspondent}")
        print(f"  Konflikte:             {plan.conflicts}")
        if args.report:
            with open(args.report, "w", encoding="utf-8-sig") as handle:
                handle.write(plan.to_report_csv())
            print(f"  Report geschrieben:    {args.report}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
