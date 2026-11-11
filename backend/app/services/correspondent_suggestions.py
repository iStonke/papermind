"""Vorschläge für offene Dokumente: zuerst vorhandene Korrespondenten, dann neu.

Ergänzt :func:`app.services.correspondent_matching.match_correspondent` (Absender
↔ Name/Alias/Matcher) um zwei Dinge für „Ohne Korrespondent“:

* :func:`clean_sender` entfernt aus dem erkannten Absender Telefonnummern,
  Anschriften und Web-/Mail-Adressen („Dr. med. Andrea, 04317/333111“ →
  „Dr. med. Andrea“).
* :func:`suggest_from_text` sucht bestehende Korrespondenten im Dokumenttext:
  ganzer Name, Kurzname oder Alias als eigenes Wort – bei Personen und Praxen
  genügt der Nachname hinter Titel oder Vorname („Dr. med. Andrea Peters“ →
  „Praxis Fr. Peters“). Der beste Treffer wird Vorschlag – bei mehreren
  gleich guten der dem Absender ähnlichste, ohne Texttreffer der namentlich
  ähnlichste vorhandene Korrespondent. Weitere Treffer sind Alternativen.

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


def _given_names(sender: str | None) -> list[str]:
    """Großgeschriebene Namenswörter des Absenders ohne Titel („Dr. med. Andrea“ → „Andrea“)."""
    return [
        word
        for word in _words(sender or "")
        if len(word) >= 3 and word[0].isupper() and word.casefold().strip(".") not in _GENERIC_WORDS
    ]


def _mentions_surname(text: str, surname: str, given_names: list[str] = ()) -> bool:
    # Nachname nur hinter Anrede/Titel oder einem großgeschriebenen Vornamen –
    # so trifft „Peters“ nicht jedes beliebige Vorkommen des Wortes.
    name = rf"{re.escape(surname)}(?![\wÄÖÜäöüß])"
    pattern = rf"(?:\b(?:Dr|Frau|Fr|Herr|Hr|Prof|med|dent|Praxis)\.?\s+|\b[A-ZÄÖÜ][a-zäöüß]+\s+){name}"
    if re.search(pattern, text):
        return True
    # Stempel/Spalten-OCR dreht oft die Reihenfolge („Peters\nAndrea“): steht ein
    # Vorname aus dem erkannten Absender direkt daneben, zählt das ebenso.
    for given in given_names:
        if given.casefold() == surname.casefold():
            continue
        first = rf"\b{re.escape(given)}(?![\wÄÖÜäöüß])"
        near = r"[\s,;:.]+(?:\S+[\s,;:.]+)?"
        if re.search(rf"{first}{near}\b{name}|\b{name}{near}{first}", text):
            return True
    return False


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
    """Bester vorhandener Korrespondent als Vorschlag und bis zu drei Alternativen."""
    pool = [
        candidate
        for candidate in candidates
        if candidate.kind != "collection" and not _is_owner(candidate, owner_names)
    ]
    corpus = _normalize(text)

    sender_words = _significant(sender or "")

    def sender_overlap(candidate: CorrespondentCandidate) -> int:
        names = correspondent_names(candidate.name, candidate.short_name, candidate.aliases)
        return max((_overlap(sender_words, _significant(name)) for name in names), default=0) if sender_words else 0

    def pick(hits: list[CorrespondentCandidate], matched_by: str):
        # Mutig: bei mehreren gleich guten Treffern wird der dem Absender
        # ähnlichste vorgeschlagen, die übrigen bleiben als Alternativen.
        unique = {candidate.correspondent_id: candidate for candidate in hits}
        ranked = sorted(unique.values(), key=lambda c: (-sender_overlap(c), -len(c.name), c.name.casefold()))
        best, rest = ranked[0], ranked[1:]
        return (
            SuggestedCorrespondent(str(best.correspondent_id), best.name, matched_by),
            [SuggestedCorrespondent(str(c.correspondent_id), c.name, "similar") for c in rest[:_MAX_SIMILAR]],
        )

    # Gleicher Name bis auf Umlaut-Schreibweise und Rechtsform („Autohaus Mueller GmbH“ ↔ „Autohaus Müller“).
    sender_key = _name_key(sender or "")
    if len(sender_key) >= 4:
        same_name = [
            candidate
            for candidate in pool
            if any(_name_key(name) == sender_key for name in correspondent_names(candidate.name, candidate.short_name, candidate.aliases))
        ]
        if same_name:
            return pick(same_name, "name")

    if corpus:
        by_name = [
            candidate
            for candidate in pool
            if mentions_any(corpus, correspondent_names(candidate.name, candidate.short_name, candidate.aliases))
        ]
        if by_name:
            return pick(by_name, "text")
        given_names = _given_names(sender)
        by_surname = [
            candidate
            for candidate in pool
            if (surname := _surname(candidate)) and _mentions_surname(corpus, surname, given_names)
        ]
        if by_surname:
            return pick(by_surname, "surname")

    # Nichts im Text: der dem Absender ähnlichste vorhandene Korrespondent wird
    # Vorschlag (vor einem neu anzulegenden), weitere bleiben Alternativen.
    if not sender_words:
        return None, []
    scored = [(overlap, candidate) for candidate in pool if (overlap := sender_overlap(candidate))]
    if not scored:
        return None, []
    scored.sort(key=lambda entry: (-entry[0], entry[1].name.casefold()))
    best = scored[0][1]
    return SuggestedCorrespondent(str(best.correspondent_id), best.name, "similar"), [
        SuggestedCorrespondent(str(candidate.correspondent_id), candidate.name, "similar")
        for _, candidate in scored[1 : _MAX_SIMILAR + 1]
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


