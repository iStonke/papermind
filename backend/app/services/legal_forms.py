"""Rechtsformen in Korrespondenten- und Absendernamen.

Die Rechtsform („GmbH", „AG", „e.V." …) gehört zum offiziellen Namen, ist aber
kein Identitätsmerkmal: „Vodafone" und „Vodafone GmbH" bezeichnen denselben
Absender. Dieses Modul ist die einzige Stelle, die Rechtsformen erkennt; das
Frontend spiegelt es in ``frontend/src/utils/legalForms.js``. Beide prüfen gegen
``backend/tests/fixtures/legal_forms.json``.

Grundregeln:
- Abgetrennt wird nur am Namensende und nur, wenn davor noch ein Name steht
  („AG Kiel" = Amtsgericht bleibt unverändert).
- Zweibuchstabige Kürzel (AG, SE, KG, UG, eG) zählen nur in ihrer üblichen
  Schreibweise, damit gewöhnliche Wortenden nicht abgeschnitten werden.
- Zwei Namen gelten als gleichwertig, wenn ihr Kern übereinstimmt und die
  Rechtsformen nicht widersprechen („Müller GmbH" ≠ „Müller KG").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_DOT = r"\.?"
_SP = r"\s*"
_AND = r"\s*(?:&|\+|und)\s*"
_CO = rf"Co{_DOT}"


def _ci(pattern: str) -> tuple[str, int]:
    return pattern, re.IGNORECASE


def _cs(pattern: str) -> tuple[str, int]:
    return pattern, 0


_UG = rf"UG{_SP}\(\s*haftungsbeschr(?:ä|ae|a)nkt\s*\)"
_GMBH = r"GmbH"

# (kanonische Schreibweise, (Muster, Flags)). Reihenfolge ist egal: gewählt wird
# der am weitesten links beginnende Treffer, also immer die längste Endung.
_FORMS: tuple[tuple[str, tuple[str, int]], ...] = (
    # Kombinationen
    ("GmbH & Co. KGaA", _ci(rf"{_GMBH}{_AND}{_CO}{_SP}KGaA")),
    ("GmbH & Co. KG", _ci(rf"{_GMBH}{_AND}{_CO}{_SP}KG")),
    ("UG (haftungsbeschränkt) & Co. KG", _ci(rf"{_UG}{_AND}{_CO}{_SP}KG")),
    ("AG & Co. KGaA", _ci(rf"AG{_AND}{_CO}{_SP}KGaA")),
    ("AG & Co. KG", _ci(rf"AG{_AND}{_CO}{_SP}KG")),
    ("SE & Co. KGaA", _ci(rf"SE{_AND}{_CO}{_SP}KGaA")),
    ("SE & Co. KG", _ci(rf"SE{_AND}{_CO}{_SP}KG")),
    ("& Co. KG", _ci(rf"(?:&|\+|und){_SP}{_CO}{_SP}KG")),
    ("PartG mbB", _ci(rf"PartG{_SP}mbB")),
    ("UG (haftungsbeschränkt)", _ci(_UG)),
    # Deutsch
    ("gGmbH", _cs(r"gGmbH")),
    ("GmbH", _ci(_GMBH)),
    ("mbH", _cs(r"mbH")),
    ("KGaA", _ci(r"KGaA")),
    ("VVaG", _ci(r"VVaG")),
    ("OHG", _ci(r"OHG")),
    ("GbR", _ci(r"GbR")),
    ("PartG", _ci(r"PartG")),
    ("AöR", _ci(r"A(?:ö|oe)R")),
    ("KdöR", _ci(r"Kd(?:ö|oe)R")),
    ("e.V.", _ci(rf"e{_DOT}{_SP}V{_DOT}")),
    ("e.K.", _ci(rf"e{_DOT}{_SP}K(?:fm|fr|fn)?{_DOT}")),
    ("eG", _cs(r"eG")),
    ("AG", _cs(r"AG")),
    ("SE", _cs(r"SE")),
    ("KG", _cs(r"KG")),
    ("UG", _cs(r"UG")),
    # International
    ("Ltd.", _ci(rf"Ltd{_DOT}|Limited")),
    ("Inc.", _ci(rf"Inc{_DOT}|Incorporated")),
    ("LLC", _ci(rf"L{_DOT}L{_DOT}C{_DOT}")),
    ("Corp.", _ci(rf"Corp{_DOT}|Corporation")),
    ("plc", _ci(r"plc")),
    ("B.V.", _cs(rf"B{_DOT}{_SP}V{_DOT}")),
    ("N.V.", _cs(rf"N{_DOT}{_SP}V{_DOT}")),
    ("S.A.", _cs(rf"S{_DOT}{_SP}A{_DOT}")),
    ("S.à r.l.", _ci(rf"S{_DOT}{_SP}(?:à|a){_SP}r{_DOT}{_SP}l{_DOT}")),
    ("S.r.l.", _ci(rf"S{_DOT}{_SP}r{_DOT}{_SP}l{_DOT}")),
    ("SAS", _cs(r"S\.?A\.?S\.?")),
)

# Vor der Rechtsform: Leerzeichen oder Komma; danach höchstens Satzzeichen.
_SUFFIX_PATTERNS = tuple(
    (canonical, re.compile(rf"[\s,]+(?:{pattern})[\s.,;:]*$", flags))
    for canonical, (pattern, flags) in _FORMS
)
# Irgendwo im Text als eigenes Wort (für „sieht nach Organisation aus").
_ANYWHERE_PATTERNS = tuple(
    (canonical, re.compile(rf"(?<![\wÄÖÜäöüß])(?:{pattern})(?![\wÄÖÜäöüß])", flags))
    for canonical, (pattern, flags) in _FORMS
)
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_RE = re.compile(r"[\s.,;:\-–]+$")
_HAS_WORD_RE = re.compile(r"[0-9A-Za-zÄÖÜäöüßÀ-ÿ]")


@dataclass(frozen=True)
class LegalFormSplit:
    base: str
    legal_form: str | None


def _clean(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return _WHITESPACE_RE.sub(" ", text).strip()


def split_legal_form(value: object) -> LegalFormSplit:
    """Name in Kern und kanonische Rechtsform am Ende zerlegen."""
    text = _clean(value)
    best: tuple[int, str] | None = None
    for canonical, pattern in _SUFFIX_PATTERNS:
        match = pattern.search(text)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), canonical)
    if best is None:
        return LegalFormSplit(text, None)
    base = _TRAILING_RE.sub("", text[: best[0]]).strip()
    if not _HAS_WORD_RE.search(base):
        return LegalFormSplit(text, None)
    return LegalFormSplit(base, best[1])


def strip_legal_form(value: object) -> str:
    """Name ohne Rechtsform am Ende („Vodafone GmbH" → „Vodafone")."""
    return split_legal_form(value).base


def canonicalize_legal_form(value: object) -> str:
    """Rechtsform am Ende in übliche Schreibweise bringen („vodafone gmbh" → „vodafone GmbH")."""
    split = split_legal_form(value)
    return f"{split.base} {split.legal_form}" if split.legal_form else split.base


def contains_legal_form(value: object) -> bool:
    """Steht irgendwo im Text eine Rechtsform als eigenes Wort?"""
    text = _clean(value)
    return any(pattern.search(text) for _, pattern in _ANYWHERE_PATTERNS)


def cut_at_legal_form(value: object) -> str:
    """Text vor der ersten Rechtsform (Rest ist meist Abteilung/Adresse).

    „Vodafone GmbH Kundenservice" → „Vodafone". Steht die Rechtsform am Anfang
    („AG Kiel"), bleibt der Text unverändert.
    """
    text = _clean(value)
    first: int | None = None
    for _, pattern in _ANYWHERE_PATTERNS:
        for match in pattern.finditer(text):
            head = _TRAILING_RE.sub("", text[: match.start()]).strip()
            if _HAS_WORD_RE.search(head):
                if first is None or match.start() < first:
                    first = match.start()
                break
    if first is None:
        return text
    return _TRAILING_RE.sub("", text[:first]).strip()


def legal_form_key(value: object) -> str:
    """Vergleichsschlüssel ohne Rechtsform, Groß-/Kleinschreibung egal."""
    return strip_legal_form(value).casefold()


def names_equivalent(left: object, right: object) -> bool:
    """Gleicher Kern und keine widersprüchlichen Rechtsformen."""
    a = split_legal_form(left)
    b = split_legal_form(right)
    if not a.base or a.base.casefold() != b.base.casefold():
        return False
    return a.legal_form is None or b.legal_form is None or a.legal_form == b.legal_form
