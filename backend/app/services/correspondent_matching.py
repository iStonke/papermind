"""Auflösung roher Absender-/Textbefunde auf kanonische Korrespondenten.

Strategie (AP10, Schritt 5): zuerst deterministisch über Aliase und Matcher,
das LLM liefert nur einen Hinweis. Die eigentliche Matching-Logik
(:func:`match_correspondent`) ist eine reine Funktion über In-Memory-Kandidaten
und damit ohne Datenbank testbar. :class:`CorrespondentMatchingService` lädt die
Kandidaten aus der DB und ruft sie auf.
"""

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.correspondent import Correspondent

logger = logging.getLogger("papermind.correspondent_matching")

_WHITESPACE_RE = re.compile(r"\s+")
_MIN_CONTAINS_LEN = 3

# Score-Bänder, höchster Treffer gewinnt.
_SCORE_NAME_EXACT = 10000
_SCORE_ALIAS_EXACT = 9000
_SCORE_MATCHER_BASE = 1000
_SCORE_ALIAS_CONTAINS = 500


@dataclass(frozen=True)
class MatcherSpec:
    kind: str  # 'contains' | 'regex' | 'starts_with'
    pattern: str
    scope: str = "both"  # 'filename' | 'ocr_text' | 'both'
    priority: int = 100


@dataclass(frozen=True)
class CorrespondentCandidate:
    correspondent_id: uuid.UUID
    name: str
    short_name: str | None = None
    aliases: tuple[str, ...] = ()
    matchers: tuple[MatcherSpec, ...] = ()


@dataclass(frozen=True)
class CorrespondentMatch:
    correspondent_id: uuid.UUID
    name: str
    short_name: str | None
    matched_by: str  # 'name' | 'alias' | 'matcher'
    matched_value: str
    score: int


@dataclass
class _ScoredMatch:
    score: int
    matched_by: str
    matched_value: str
    candidate: CorrespondentCandidate = field(repr=False)


def _normalize(value: str | None) -> str:
    # Unicode auf NFC vereinheitlichen: macOS-Dateinamen/Tags liegen zerlegt (NFD)
    # vor (z. B. "ö" = o + ◌̈), die DB-Werte zusammengesetzt. Ohne Angleichung
    # schlägt der Vergleich bei Umlauten fehl.
    normalized = unicodedata.normalize("NFC", str(value or ""))
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _matcher_hits(spec: MatcherSpec, text: str) -> bool:
    pattern = _normalize(spec.pattern)
    if not pattern or not text:
        return False
    lowered_text = text.casefold()
    lowered_pattern = pattern.casefold()
    if spec.kind == "contains":
        return lowered_pattern in lowered_text
    if spec.kind == "starts_with":
        return lowered_text.startswith(lowered_pattern)
    if spec.kind == "regex":
        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error as exc:  # noqa: BLE001 - ungültige Regex darf das Matching nicht abbrechen
            logger.warning("invalid correspondent matcher regex %r: %s", pattern, exc)
            return False
    return False


def _matcher_corpora(scope: str, *, sender: str, filename: str, ocr_text: str) -> list[str]:
    # Der rohe Absender ist das primäre Signal und wird immer geprüft; der Scope
    # steuert nur die zusätzlich durchsuchten Korpora.
    corpora = [sender] if sender else []
    if scope in ("filename", "both") and filename:
        corpora.append(filename)
    if scope in ("ocr_text", "both") and ocr_text:
        corpora.append(ocr_text)
    return corpora


def match_correspondent(
    candidates: list[CorrespondentCandidate],
    *,
    sender: str | None = None,
    filename: str | None = None,
    ocr_text: str | None = None,
) -> CorrespondentMatch | None:
    """Besten Korrespondenten für die gegebenen Rohtexte bestimmen, oder ``None``.

    Reihenfolge der Sicherheit: exakter Name > exakter Alias > Matcher > Alias als
    Teilstring. Bei Gleichstand gewinnt der längere Treffer, dann der Name.
    """
    sender_norm = _normalize(sender)
    filename_norm = _normalize(filename)
    ocr_norm = _normalize(ocr_text)
    sender_cf = sender_norm.casefold()

    best: _ScoredMatch | None = None

    def consider(score: int, matched_by: str, matched_value: str, candidate: CorrespondentCandidate) -> None:
        nonlocal best
        if best is None:
            best = _ScoredMatch(score, matched_by, matched_value, candidate)
            return
        challenger = (score, len(matched_value), candidate.name.casefold())
        incumbent = (best.score, len(best.matched_value), best.candidate.name.casefold())
        # Höherer Score gewinnt; bei Gleichstand längerer Treffer, dann Name (stabil).
        if (challenger[0], challenger[1]) > (incumbent[0], incumbent[1]) or (
            (challenger[0], challenger[1]) == (incumbent[0], incumbent[1]) and challenger[2] < incumbent[2]
        ):
            best = _ScoredMatch(score, matched_by, matched_value, candidate)

    for candidate in candidates:
        name_norm = _normalize(candidate.name)
        if sender_cf and name_norm and name_norm.casefold() == sender_cf:
            consider(_SCORE_NAME_EXACT + len(name_norm), "name", name_norm, candidate)

        for alias in candidate.aliases:
            alias_norm = _normalize(alias)
            if not alias_norm:
                continue
            alias_cf = alias_norm.casefold()
            if sender_cf and alias_cf == sender_cf:
                consider(_SCORE_ALIAS_EXACT + len(alias_norm), "alias", alias_norm, candidate)
            elif sender_cf and len(alias_norm) >= _MIN_CONTAINS_LEN and alias_cf in sender_cf:
                consider(_SCORE_ALIAS_CONTAINS + len(alias_norm), "alias", alias_norm, candidate)

        for spec in candidate.matchers:
            corpora = _matcher_corpora(
                spec.scope,
                sender=sender_norm,
                filename=filename_norm,
                ocr_text=ocr_norm,
            )
            if any(_matcher_hits(spec, text) for text in corpora):
                consider(
                    _SCORE_MATCHER_BASE + int(spec.priority or 0),
                    "matcher",
                    _normalize(spec.pattern),
                    candidate,
                )

    if best is None:
        return None
    return CorrespondentMatch(
        correspondent_id=best.candidate.correspondent_id,
        name=best.candidate.name,
        short_name=best.candidate.short_name,
        matched_by=best.matched_by,
        matched_value=best.matched_value,
        score=best.score,
    )


class CorrespondentMatchingService:
    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id

    def load_candidates(self) -> list[CorrespondentCandidate]:
        stmt = select(Correspondent).options(
            selectinload(Correspondent.aliases),
            selectinload(Correspondent.matchers),
        )
        if self.owner_id is not None:
            stmt = stmt.where(Correspondent.owner_id == self.owner_id)
        correspondents = self.db.execute(stmt).scalars().all()
        candidates: list[CorrespondentCandidate] = []
        for correspondent in correspondents:
            candidates.append(
                CorrespondentCandidate(
                    correspondent_id=correspondent.id,
                    name=correspondent.name,
                    short_name=correspondent.short_name,
                    aliases=tuple(alias.alias for alias in correspondent.aliases),
                    matchers=tuple(
                        MatcherSpec(
                            kind=matcher.kind,
                            pattern=matcher.pattern,
                            scope=matcher.scope,
                            priority=matcher.priority,
                        )
                        for matcher in correspondent.matchers
                    ),
                )
            )
        return candidates

    def resolve(
        self,
        *,
        sender: str | None = None,
        filename: str | None = None,
        ocr_text: str | None = None,
    ) -> CorrespondentMatch | None:
        if not any(_normalize(value) for value in (sender, filename, ocr_text)):
            return None
        return match_correspondent(
            self.load_candidates(),
            sender=sender,
            filename=filename,
            ocr_text=ocr_text,
        )
