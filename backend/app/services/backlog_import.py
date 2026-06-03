"""Trockenlauf-Planung für den Altbestand-Import (AP10 Schritt 9).

Liest eine CSV (Dateiname,Tags) plus einen PDF-Ordner und plant je Dokument:
- welcher alte Tag ein kanonischer Korrespondent ist (über das Matching),
- welche Tags Sach-Tags bleiben,
- welcher Dateiname/Anzeigename gesetzt würde,
- sowie Konflikte (fehlende PDFs, PDFs ohne CSV-Zeile, mehrdeutige Korrespondenten).

Reine Planung – es wird nichts geschrieben und nichts importiert.
"""

from __future__ import annotations

import csv as csv_module
import io
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.correspondent_matching import CorrespondentMatchingService

# Ab diesem Score gilt ein Tag als kanonischer Korrespondent (exakter Name/Alias
# liegt deutlich darüber; reine contains-Matcher knapp darüber).
_MIN_CORRESPONDENT_SCORE = 500


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", str(value or ""))


@dataclass(frozen=True)
class BacklogTagDecision:
    tag: str
    decision: str  # 'correspondent' | 'topic'
    correspondent_id: str | None = None
    correspondent_name: str | None = None
    matched_by: str | None = None
    score: int | None = None


@dataclass(frozen=True)
class BacklogDocPlan:
    filename: str
    pdf_exists: bool
    display_name: str
    raw_tags: tuple[str, ...]
    correspondent_id: str | None
    correspondent_name: str | None
    correspondent_conflict: tuple[str, ...]
    topic_tags: tuple[str, ...]
    tag_decisions: tuple[BacklogTagDecision, ...]


@dataclass
class BacklogPlan:
    total_rows: int
    pdfs_in_folder: int
    matched_pdf: int
    missing_pdf: list[str] = field(default_factory=list)
    extra_pdf: list[str] = field(default_factory=list)
    with_correspondent: int = 0
    conflicts: int = 0
    docs: list[BacklogDocPlan] = field(default_factory=list)
    correspondent_tag_counts: dict[str, int] = field(default_factory=dict)
    topic_tag_counts: dict[str, int] = field(default_factory=dict)

    def to_report_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv_module.writer(buffer)
        writer.writerow(
            ["Dateiname", "PDF vorhanden", "Korrespondent", "Konflikt", "Sach-Tags", "Anzeigename"]
        )
        for doc in self.docs:
            writer.writerow(
                [
                    doc.filename,
                    "ja" if doc.pdf_exists else "FEHLT",
                    doc.correspondent_name or "",
                    "; ".join(doc.correspondent_conflict),
                    ", ".join(doc.topic_tags),
                    doc.display_name,
                ]
            )
        return buffer.getvalue()


def parse_backlog_csv(content: str) -> list[tuple[str, list[str]]]:
    """CSV ``Dateiname,Tags`` parsen. Tags innerhalb einer Zelle sind komma-getrennt.

    Liefert ``(dateiname, [tag, ...])``. Die Kopfzeile wird übersprungen.
    """
    rows: list[tuple[str, list[str]]] = []
    reader = csv_module.reader(io.StringIO(content))
    for index, fields in enumerate(reader):
        if not fields:
            continue
        filename = (fields[0] or "").strip()
        if not filename:
            continue
        if index == 0 and filename.lower() in {"dateiname", "filename", "name"}:
            continue  # Header
        raw_tags = fields[1] if len(fields) > 1 else ""
        tags = [tag.strip() for tag in str(raw_tags or "").split(",") if tag.strip()]
        # Duplikate (case-insensitiv) entfernen, Reihenfolge erhalten
        seen: set[str] = set()
        deduped: list[str] = []
        for tag in tags:
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                deduped.append(tag)
        rows.append((filename, deduped))
    return rows


def _strip_extension(filename: str) -> str:
    return Path(filename).stem.strip() or filename.strip()


class BacklogImportService:
    def __init__(self, db: Session):
        self.db = db
        self.matcher = CorrespondentMatchingService(db)
        # Korrespondenten-Kandidaten einmal laden (für viele Tags wiederverwenden).
        self._candidates = self.matcher.load_candidates()

    def _classify_tag(self, tag: str) -> BacklogTagDecision:
        from app.services.correspondent_matching import match_correspondent

        match = match_correspondent(self._candidates, sender=tag)
        if match is not None and match.score >= _MIN_CORRESPONDENT_SCORE:
            return BacklogTagDecision(
                tag=tag,
                decision="correspondent",
                correspondent_id=str(match.correspondent_id),
                correspondent_name=match.name,
                matched_by=match.matched_by,
                score=match.score,
            )
        return BacklogTagDecision(tag=tag, decision="topic")

    def plan(self, *, csv_content: str, pdf_dir: str | Path) -> BacklogPlan:
        rows = parse_backlog_csv(csv_content)
        pdf_path = Path(pdf_dir)
        # Dateinamen NFC-normalisiert vergleichen (macOS liefert NFD).
        folder_files = {_nfc(p.name) for p in pdf_path.glob("*.pdf")} if pdf_path.is_dir() else set()

        docs: list[BacklogDocPlan] = []
        correspondent_tag_counts: Counter[str] = Counter()
        topic_tag_counts: Counter[str] = Counter()
        with_correspondent = 0
        conflicts = 0
        csv_filenames: set[str] = set()

        for filename, tags in rows:
            filename_nfc = _nfc(filename)
            csv_filenames.add(filename_nfc)
            decisions = [self._classify_tag(tag) for tag in tags]

            correspondent_names: list[str] = []
            correspondent_id: str | None = None
            correspondent_name: str | None = None
            topic_tags: list[str] = []
            for decision in decisions:
                if decision.decision == "correspondent" and decision.correspondent_name:
                    correspondent_tag_counts[decision.tag] += 1
                    if decision.correspondent_name not in correspondent_names:
                        correspondent_names.append(decision.correspondent_name)
                    if correspondent_id is None:
                        correspondent_id = decision.correspondent_id
                        correspondent_name = decision.correspondent_name
                else:
                    topic_tag_counts[decision.tag] += 1
                    topic_tags.append(decision.tag)

            conflict = tuple(correspondent_names) if len(correspondent_names) > 1 else ()
            if conflict:
                conflicts += 1
            if correspondent_name:
                with_correspondent += 1

            # Nur PDFs interessieren für den Datei-Abgleich.
            is_pdf = filename.lower().endswith(".pdf")
            pdf_exists = filename_nfc in folder_files if is_pdf else False

            docs.append(
                BacklogDocPlan(
                    filename=filename,
                    pdf_exists=pdf_exists,
                    display_name=_nfc(_strip_extension(filename)),
                    raw_tags=tuple(tags),
                    correspondent_id=correspondent_id,
                    correspondent_name=correspondent_name,
                    correspondent_conflict=conflict,
                    topic_tags=tuple(topic_tags),
                    tag_decisions=tuple(decisions),
                )
            )

        pdf_rows = [doc for doc in docs if doc.filename.lower().endswith(".pdf")]
        missing_pdf = [doc.filename for doc in pdf_rows if not doc.pdf_exists]
        extra_pdf = sorted(folder_files - csv_filenames)
        matched_pdf = sum(1 for doc in pdf_rows if doc.pdf_exists)

        return BacklogPlan(
            total_rows=len(rows),
            pdfs_in_folder=len(folder_files),
            matched_pdf=matched_pdf,
            missing_pdf=missing_pdf,
            extra_pdf=extra_pdf,
            with_correspondent=with_correspondent,
            conflicts=conflicts,
            docs=docs,
            correspondent_tag_counts=dict(correspondent_tag_counts),
            topic_tag_counts=dict(topic_tag_counts),
        )
