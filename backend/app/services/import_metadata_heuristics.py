"""Lokale Heuristiken für Absender und einfachen Dokumentbetreff."""

from __future__ import annotations

import re

from app.services.import_metadata_rules import normalize_document_type
from app.services.import_title_formatting import clean_filename_component, normalize_text

_SENDER_LINE_HINTS = ("gmbh", "ag", "kg", "ug", "mbh", "ev", "e.v", "gbr", "ohg", "kasse", "auto-service")
_SENDER_ORG_HINTS = (
    "verein", "sportverein", "bank", "sparkasse", "versicherung", "service", "werkstatt", "praxis", "klinik", "stadtwerke",
)
_ISSUER_SUFFIX_RE = re.compile(r"\b(gmbh|ag|ug|kg|e\.?\s?v\.?|ltd|inc)\b\.?", re.IGNORECASE)
_TRAILING_PUNCT_RE = re.compile(r"[.,;:\-–\s]+$")
_ISSUER_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß0-9&.\-]+")
_ISSUER_STOP_TOKENS = frozenset({
    "herr", "frau", "dr", "prof", "an", "z.hd", "idnr", "idnr.", "steuernr", "steuernummer", "ustidnr", "ust-id",
    "kundennr", "kundennummer", "auftragsnr", "rechnungsnr", "tel", "fax", "postfach", "str", "straße", "strasse", "plz",
    "www", "http", "https", "info@", "kontakt",
})
SUBJECT_HINTS: dict[str, tuple[str, ...]] = {
    "Hauptuntersuchung": ("hauptuntersuchung", "tüv", "tuev", " hu ", "abgas", "au "),
    "Kfz-Service": ("auto-service", "werkstatt", "inspektion", "reparatur", "kfz", "fahrzeug"),
    "Versicherung": ("versicherung", "police", "versicherungsschein"),
    "Vodafone": ("vodafone",),
    "Energie": ("strom", "energie", "gas", "abschlag", "kilowatt"),
    "Kündigung": ("kündigung", "kuendigung"),
}
_SUBJECT_HEADING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(Einkommensteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Lohnsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Umsatzsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Körperschaftsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Gewerbesteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Grundsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Rentenbescheid|Renteninformation)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Jahresabrechnung)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Kontoauszug)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Kreditkartenabrechnung)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Gehaltsabrechnung|Lohnabrechnung|Gehaltsnachweis)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Nebenkostenabrechnung|Betriebskostenabrechnung)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Versicherungsschein|Police)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Mietvertrag)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Arbeitsvertrag)\b", re.IGNORECASE), "{0}"),
]
_TAG_KEYWORD_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("einkommensteuer",), ["Einkommensteuer", "Steuer"]), (("lohnsteuer",), ["Lohnsteuer", "Steuer"]),
    (("umsatzsteuer",), ["Umsatzsteuer", "Steuer"]), (("körperschaftsteuer", "koerperschaftsteuer"), ["Körperschaftsteuer", "Steuer"]),
    (("gewerbesteuer",), ["Gewerbesteuer", "Steuer"]), (("grundsteuer",), ["Grundsteuer", "Steuer"]),
    (("kindergeld",), ["Kindergeld"]), (("rentenbescheid", "renteninformation", "rentenversicherung"), ["Rente", "Rentenversicherung"]),
    (("krankenversicherung", "gesundheitsversicherung"), ["Krankenversicherung", "Gesundheit"]), (("pflegeversicherung",), ["Pflegeversicherung"]),
    (("unfallversicherung",), ["Unfallversicherung"]), (("haftpflichtversicherung", "haftpflicht"), ["Haftpflicht", "Versicherung"]),
    (("kfz-versicherung", "kraftfahrzeugversicherung", "fahrzeugversicherung"), ["KFZ-Versicherung", "Auto"]), (("lebensversicherung",), ["Lebensversicherung"]),
    (("strom", "stromverbrauch", "kilowattstunde", "kwh"), ["Strom", "Energie"]), (("gasverbrauch", "erdgas", "gasversorger"), ["Gas", "Energie"]),
    (("wasserverbrauch", "trinkwasser", "abwasser"), ["Wasser"]), (("fernwärme", "heizung", "heizkosten"), ["Heizung", "Energie"]),
    (("internetanschluss", "internettarif", "dsl", "breitband", "glasfaser"), ["Internet", "Telekommunikation"]),
    (("mobilfunk", "handy", "smartphone", "vodafone", "telekom", "o2 ", "congstar"), ["Mobilfunk", "Telekommunikation"]),
    (("festnetz", "telefon"), ["Telefon", "Telekommunikation"]), (("miete", "mietvertrag", "kaltmiete", "warmmiete"), ["Miete", "Wohnen"]),
    (("nebenkosten", "betriebskosten", "hausgeld"), ["Nebenkosten", "Wohnen"]), (("arzt", "praxis", "behandlung", "untersuchung", "osteopathie", "physiotherapie", "zahnarzt", "orthopädie"), ["Arzt", "Gesundheit"]),
    (("apotheke", "medikament", "rezept"), ["Apotheke", "Gesundheit"]), (("krankenhaus", "klinik", "station"), ["Krankenhaus", "Gesundheit"]),
    (("gehaltsabrechnung", "lohnabrechnung", "gehaltsnachweis", "entgeltabrechnung"), ["Gehalt", "Arbeit"]), (("arbeitsvertrag",), ["Arbeitsvertrag", "Arbeit"]),
    (("kündigung",), ["Kündigung"]), (("mietvertrag",), ["Mietvertrag", "Wohnen"]), (("kontoauszug", "kontoumsätze"), ["Kontoauszug", "Bank"]),
    (("kreditkarte", "kreditkartenabrechnung"), ["Kreditkarte", "Bank"]), (("darlehen", "kredit", "tilgung", "zinsen"), ["Kredit", "Bank"]),
    (("depot", "wertpapier", "aktie", "fonds"), ["Geldanlage", "Bank"]), (("finanzamt",), ["Finanzamt", "Steuer"]),
]


def normalize_issuer(value: object) -> str:
    normalized = clean_filename_component(value, max_len=40)
    normalized = normalized.replace(" - ", " ").replace(" – ", " ")
    normalized = _ISSUER_SUFFIX_RE.sub("", normalized)
    normalized = _TRAILING_PUNCT_RE.sub("", normalized).strip()
    return normalized[:30].rstrip(" .,-") if len(normalized) > 30 else normalized


def extract_issuer_from_line(line: object) -> str:
    compact = normalize_text(line)
    if not compact:
        return ""
    head = compact.split(",")[0].strip() or compact
    head = re.sub(r"^[^A-Za-zÄÖÜäöüß0-9]+", "", head).strip()
    if not head:
        return ""
    head_tokens = head.split()
    for group_size in range(len(head_tokens) // 2, 0, -1):
        if head_tokens[:group_size] == head_tokens[group_size : group_size * 2]:
            head = " ".join(head_tokens[:group_size])
            break
    cleaned_tokens: list[str] = []
    for token in _ISSUER_TOKEN_RE.findall(head):
        lowered = token.lower().rstrip(".")
        if not re.search(r"[a-zäöüß0-9]", lowered):
            continue
        if lowered in _ISSUER_STOP_TOKENS or re.fullmatch(r"\d+[a-zA-Z]?", token):
            break
        cleaned_tokens.append(token)
        if len(cleaned_tokens) >= 6:
            break
    return normalize_issuer(" ".join(cleaned_tokens).strip())


def normalize_subject(value: object) -> str:
    normalized = clean_filename_component(value, max_len=60)
    normalized = normalized.replace(" - ", " ").replace(" – ", " ")
    normalized = re.sub(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b", "", normalized)
    normalized = re.sub(r"\b(?:rechnungsnummer|rechnung\s*nr|invoice\s*no|belegnummer|belegnr)\b.*$", "", normalized, flags=re.IGNORECASE)
    normalized = " ".join(normalized.split()).strip(" .,-_")
    return normalized[:40].rstrip(" .,-_") if len(normalized) > 40 else normalized


def detect_sender(text_value: object) -> str | None:
    lines = [line.strip() for line in str(text_value or "").splitlines() if line.strip()]
    candidates = lines[:20]
    scored_candidates: list[tuple[int, int, str]] = []
    for index, line in enumerate(candidates):
        if any(hint in line.lower() for hint in _SENDER_LINE_HINTS):
            issuer = extract_issuer_from_line(line)
            if issuer and len(issuer) >= 4:
                scored_candidates.append((120 - index, index, issuer))
    for index, line in enumerate(candidates):
        if 2 <= len(line.split()) <= 6 and len(line) <= 44 and not any(char.isdigit() for char in line):
            issuer = normalize_issuer(line)
            if issuer and len(issuer) >= 4:
                score = 30 - index + (60 if any(hint in issuer.lower() for hint in _SENDER_ORG_HINTS) else 0)
                scored_candidates.append((score, index, issuer))
    for index, line in enumerate(candidates[:8]):
        issuer = extract_issuer_from_line(line)
        if not issuer or issuer.lower() in {"herr", "frau"} or re.search(r"\b\d{3,}\b", issuer) or len(issuer) < 4:
            continue
        score = 20 - index + (60 if any(hint in issuer.lower() for hint in _SENDER_ORG_HINTS) else 0)
        scored_candidates.append((score, index, issuer))
    if not scored_candidates:
        return None
    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    return scored_candidates[0][2]


def detect_subject_heuristic(text_value: object) -> str:
    normalized = f" {str(text_value or '').lower()} "
    if any(token in normalized for token in SUBJECT_HINTS["Hauptuntersuchung"]):
        return "Hauptuntersuchung"
    if any(token in normalized for token in SUBJECT_HINTS["Kfz-Service"]):
        return "Kfz-Service"
    if "versicherung" in normalized:
        return "Versicherung"
    if "vodafone" in normalized:
        return "Vodafone"
    if any(token in normalized for token in SUBJECT_HINTS["Energie"]):
        return "Energie"
    return "Kündigung" if "kündigung" in normalized or "kuendigung" in normalized else "Ohne Betreff"


def is_subject_supported_by_context(subject: object, text_value: object, issuer_value: object = "") -> bool:
    normalized_subject = normalize_subject(subject).lower()
    if not normalized_subject or len(normalized_subject.split()) > 5:
        return False
    context = f" {str(text_value or '').lower()} {str(issuer_value or '').lower()} "
    known = {key.lower(): key for key in SUBJECT_HINTS}
    if normalized_subject in known:
        return any(token in context for token in SUBJECT_HINTS[known[normalized_subject]])
    return normalized_subject != "ohne betreff"


def extract_subject_rich(text_value: object, _doc_type: str) -> str | None:
    text = str(text_value or "")
    lower = text.lower()
    for keyword, label in (("einkommensteuer", "Einkommensteuer"), ("lohnsteuer", "Lohnsteuer"), ("umsatzsteuer", "Umsatzsteuer"), ("körperschaftsteuer", "Körperschaftsteuer"), ("koerperschaftsteuer", "Körperschaftsteuer"), ("gewerbesteuer", "Gewerbesteuer"), ("grundsteuer", "Grundsteuer")):
        if keyword in lower:
            year_match = re.search(r"\b(?:f[üu]r|steuerjahr|est|zur|jahr)\s+(20\d{2})\b", text, re.IGNORECASE) or re.search(r"\b(20\d{2})\b", text)
            return f"{label} {year_match.group(1)}" if year_match else label
    match = re.search(r"\bbescheid\s+f[üu]r\s+(20\d{2})\s+[üu]ber\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{4,30})", text, re.IGNORECASE)
    if match:
        raw_type = " ".join(match.group(2).split())[:30].strip()
        if re.fullmatch(r"(?:[A-Za-zÄÖÜäöüß] +){3,}[A-Za-zÄÖÜäöüß]", raw_type):
            raw_type = re.sub(r"\s+", "", raw_type)
        return f"{raw_type} {match.group(1)}"
    for pattern, fmt in _SUBJECT_HEADING_PATTERNS:
        match = pattern.search(text)
        if match:
            return fmt.format(*(match.group(index + 1) for index in range(len(match.groups()))))
    return None


def generate_tags_from_text(text_value: object, doc_type: str) -> list[str]:
    clean = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", str(text_value or ""), flags=re.IGNORECASE)
    lower = clean.lower()
    tags: list[str] = []
    def add_tag(tag: str) -> None:
        if tag not in tags and len(tags) < 2:
            tags.append(tag)
    normalized_doc_type = normalize_document_type(doc_type) or ""
    if normalized_doc_type == "Kündigung":
        add_tag("Kündigung")
        if re.search(r"\b(mitgliedschaft|verein|sportverein|turnverein)\b", lower):
            add_tag("Mitgliedschaft")
    elif normalized_doc_type == "Rechnung":
        add_tag("Rechnung")
    telecom_context = any(re.search(r"\b" + re.escape(keyword) + r"\b", lower) for keyword in ("telefonrechnung", "telefonvertrag", "telefonanschluss", "internettarif", "internetanschluss", "mobilfunk", "handyvertrag", "dsl", "glasfaser", "vodafone", "telekom", "congstar"))
    for keywords, tag_list in _TAG_KEYWORD_RULES:
        if len(tags) >= 2:
            break
        matched = any(re.search(r"\b" + re.escape(keyword) + r"\b", lower) for keyword in keywords)
        if matched and set(tag_list).issubset({"Telefon", "Telekommunikation"}) and not telecom_context:
            continue
        if matched:
            for tag in tag_list:
                add_tag(tag)
    return tags
