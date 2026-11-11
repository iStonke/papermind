"""Vorschläge für offene Dokumente: zuerst vorhandene Korrespondenten, dann neu.

Ergänzt :func:`app.services.correspondent_matching.match_correspondent` (Absender
↔ Name/Alias/Matcher) um zwei Dinge für „Ohne Korrespondent“:

* :func:`clean_sender` entfernt aus dem erkannten Absender Telefonnummern,
  Anschriften und Web-/Mail-Adressen („Dr. med. Andrea, 04317/333111“ →
  „Dr. med. Andrea“).
* :func:`suggest_from_text` sucht bestehende Korrespondenten im Dokumenttext:
  ganzer Name, Kurzname oder Alias als eigenes Wort – bei Personen und Praxen
  genügt der Nachname hinter Titel oder Vorname („Dr. med. Andrea Peters“ →
  „Praxis Fr. Peters“). Eindeutige Treffer werden Vorschlag; mehrere gleich
  gute Treffer bzw. Namensähnlichkeiten mit dem Absender werden nur als
  „ähnlich“ gemeldet.

Reine Funktionen über In-Memory-Kandidaten, ohne Datenbank testbar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.correspondent_matching import (
    CorrespondentCandidate,
    _normalize,
    correspondent_names,
    mentions_any,
)
from app.services.legal_forms import contains_legal_form, strip_legal_form

# ── Absender bereinigen ──────────────────────────────────────────────────────
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_MAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(
    r"(?:\b(?:tel(?:efon)?|fon|fax|mobil|handy)\.?\s*:?\s*)?\+?\(?\d[\d\s/().–-]{4,}\d",
    re.IGNORECASE,
)
_POSTCODE_CITY_RE = re.compile(r"\b(?:D-)?\d{5}\s+[A-ZÄÖÜ][\wäöüß.-]*(?:\s+[A-ZÄÖÜ][\wäöüß.-]*)?")
_STREET_RE = re.compile(
    r"\b[\wÄÖÜäöüß.-]*(?:straße|strasse|str\.|weg|platz|allee|gasse|ring|damm|chaussee)\s*\d+\s*[a-z]?\b",
    re.IGNORECASE,
)
_PARTS_RE = re.compile(r"\s*[,;|·•]\s*")
_EDGE_PUNCT = " .,;:-–—/|"


def clean_sender(value: object) -> str:
    """Absender ohne Telefon, Anschrift, Web- und Mail-Adresse.

    Enthält ein Teil (durch Komma getrennt) eine Rechtsform, bleibt nur dieser
    Teil – das ist fast immer der eigentliche Absender („Leiterin
    Personalentwicklung, coop eG Benzstraße 10 …“ → „coop eG“).
    """
    text = _normalize(value)
    if not text:
        return ""

    def drop_phone(match: re.Match) -> str:
        return " " if sum(ch.isdigit() for ch in match.group(0)) >= 6 else match.group(0)

    for pattern in (_URL_RE, _MAIL_RE, _STREET_RE, _POSTCODE_CITY_RE):
        text = pattern.sub(" ", text)
    text = _PHONE_RE.sub(drop_phone, text)
    parts = [
        _normalize(part).strip(_EDGE_PUNCT)
        for part in _PARTS_RE.split(text)
    ]
    parts = [part for part in parts if part and any(ch.isalpha() for ch in part)]
    with_legal_form = [part for part in parts if contains_legal_form(part)]
    if len(with_legal_form) == 1:
        parts = with_legal_form
    return _normalize(", ".join(parts)).strip(_EDGE_PUNCT)


# ── Vorhandene Korrespondenten im Text finden ────────────────────────────────
_TITLE_WORDS = frozenset({
    "praxis", "fr", "frau", "herr", "hr", "dr", "med", "dent", "prof", "dipl", "ing", "inh", "inhaber",
    "inhaberin", "rechtsanwalt", "rechtsanwältin", "ra", "notar", "notarin", "zahnarzt", "zahnärztin",
    "ärztin", "arzt", "physiotherapie", "kanzlei", "familie", "fam",
})
# Allgemeine Wörter, die allein keine Ähnlichkeit belegen.
_GENERIC_WORDS = _TITLE_WORDS | frozenset({
    "und", "der", "die", "das", "von", "zu", "für", "fuer", "the", "and", "of", "gmbh", "mbh", "co", "kg", "ag",
    "hotel", "autohaus", "schule", "verein", "service", "gruppe", "zentrum", "bank", "kasse", "stadt", "amt",
    "kiel", "berlin", "hamburg", "deutschland", "deutsche", "bundes", "landes",
})
_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]*")
_MAX_SIMILAR = 3


@dataclass(frozen=True)
class SuggestedCorrespondent:
    correspondent_id: str
    name: str
    matched_by: str  # 'name' | 'alias' | 'matcher' | 'member' | 'text' | 'surname' | 'similar'


def _words(value: str) -> list[str]:
    return _WORD_RE.findall(value or "")


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _name_key(value: str) -> str:
    base = (strip_legal_form(value) or value).casefold().translate(_UMLAUTS)
    return re.sub(r"[^0-9a-z]", "", base)


def _significant(value: str) -> set[str]:
    # Umlaute ausgeschrieben vergleichen: „Müller“ ↔ „Mueller“.
    return {
        word.casefold().translate(_UMLAUTS)
        for word in _words(strip_legal_form(value) or value)
        if len(word) >= 4 and word.casefold().strip(".") not in _GENERIC_WORDS
    }


def _similar_word(left: str, right: str) -> bool:
    # Gleich oder fast gleich (Tippfehler/OCR: „Börgerhof“ ↔ „Bürgerhof“).
    return left == right or (min(len(left), len(right)) >= 6 and SequenceMatcher(None, left, right).ratio() >= 0.85)


def _overlap(sender_words: set[str], name_words: set[str]) -> int:
    return sum(1 for word in name_words if any(_similar_word(word, other) for other in sender_words))


def _surname(candidate: CorrespondentCandidate) -> str | None:
    """Nachname bei Personen bzw. Namen mit Titel/Anrede („Praxis Fr. Peters“)."""
    words = _words(strip_legal_form(candidate.name) or candidate.name)
    has_title = any(word.casefold().strip(".") in _TITLE_WORDS for word in words)
    if candidate.kind != "person" and not has_title:
        return None
    rest = [word for word in words if word.casefold().strip(".") not in _TITLE_WORDS]
    surname = rest[-1] if rest else None
    return surname if surname and len(surname) >= 3 and surname[0].isupper() else None


def _mentions_surname(text: str, surname: str) -> bool:
    # Nachname nur hinter Anrede/Titel oder einem großgeschriebenen Vornamen –
    # so trifft „Peters“ nicht jedes beliebige Vorkommen des Wortes.
    pattern = (
        rf"(?:\b(?:Dr|Frau|Fr|Herr|Hr|Prof|med|dent|Praxis)\.?\s+|\b[A-ZÄÖÜ][a-zäöüß]+\s+)"
        rf"{re.escape(surname)}(?![\wÄÖÜäöüß])"
    )
    return re.search(pattern, text) is not None


def _is_owner(candidate: CorrespondentCandidate, owner_names: tuple[str, ...]) -> bool:
    """Der Empfänger (die Nutzerin/der Nutzer selbst) steht in fast jedem Brief."""
    names = {name.casefold() for name in correspondent_names(candidate.name, candidate.short_name, candidate.aliases)}
    for owner in owner_names:
        owner_cf = _normalize(owner).casefold()
        if not owner_cf:
            continue
        if owner_cf in names:
            return True
        owner_words = {word.casefold() for word in _words(owner)}
        candidate_words = {word.casefold() for word in _words(candidate.name)}
        if candidate.kind == "person" and candidate_words and candidate_words <= owner_words:
            return True
    return False


def suggest_from_text(
    candidates: list[CorrespondentCandidate],
    *,
    text: str | None,
    sender: str | None = None,
    owner_names: tuple[str, ...] = (),
) -> tuple[SuggestedCorrespondent | None, list[SuggestedCorrespondent]]:
    """Eindeutiger Vorschlag aus dem Dokumenttext und bis zu drei ähnliche Kandidaten."""
    pool = [
        candidate
        for candidate in candidates
        if candidate.kind != "collection" and not _is_owner(candidate, owner_names)
    ]
    corpus = _normalize(text)

    def pick(hits: list[CorrespondentCandidate], matched_by: str):
        unique = {candidate.correspondent_id: candidate for candidate in hits}
        if len(unique) == 1:
            candidate = next(iter(unique.values()))
            return SuggestedCorrespondent(str(candidate.correspondent_id), candidate.name, matched_by), []
        similar = [SuggestedCorrespondent(str(c.correspondent_id), c.name, "similar") for c in unique.values()]
        return None, sorted(similar, key=lambda entry: entry.name.casefold())[:_MAX_SIMILAR]

    # Gleicher Name bis auf Umlaut-Schreibweise und Rechtsform („Autohaus Mueller GmbH“ ↔ „Autohaus Müller“).
    sender_key = _name_key(sender or "")
    if len(sender_key) >= 4:
        same_name = [
            candidate
            for candidate in pool
            if any(_name_key(name) == sender_key for name in correspondent_names(candidate.name, candidate.short_name, candidate.aliases))
        ]
        if same_name:
            found, similar = pick(same_name, "name")
            if found:
                return found, similar

    if corpus:
        by_name = [
            candidate
            for candidate in pool
            if mentions_any(corpus, correspondent_names(candidate.name, candidate.short_name, candidate.aliases))
        ]
        if by_name:
            return pick(by_name, "text")
        by_surname = [
            candidate
            for candidate in pool
            if (surname := _surname(candidate)) and _mentions_surname(corpus, surname)
        ]
        if by_surname:
            return pick(by_surname, "surname")

    # Nichts Eindeutiges im Text: Namensähnlichkeit zum Absender als Hinweis.
    sender_words = _significant(sender or "")
    if not sender_words:
        return None, []
    scored: list[tuple[int, str, CorrespondentCandidate]] = []
    for candidate in pool:
        names = correspondent_names(candidate.name, candidate.short_name, candidate.aliases)
        overlap = max((_overlap(sender_words, _significant(name)) for name in names), default=0)
        if overlap:
            scored.append((overlap, candidate.name.casefold(), candidate))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return None, [
        SuggestedCorrespondent(str(candidate.correspondent_id), candidate.name, "similar")
        for _, _, candidate in scored[:_MAX_SIMILAR]
    ]


def suggestion_for(
    candidates: list[CorrespondentCandidate],
    *,
    sender: str | None,
    text: str | None,
    owner_names: tuple[str, ...] = (),
    sender_match=None,
) -> tuple[SuggestedCorrespondent | None, list[SuggestedCorrespondent]]:
    """Gesamtvorschlag: erst der Absender-Abgleich (falls übergeben), dann der Text."""
    if sender_match is not None:
        return SuggestedCorrespondent(str(sender_match.correspondent_id), sender_match.name, sender_match.matched_by), []
    return suggest_from_text(candidates, text=text, sender=sender, owner_names=owner_names)


