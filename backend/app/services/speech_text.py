"""Spoken forms for German notes; stored note content is never modified."""

import re
from datetime import date
from decimal import Decimal

from app.schemas.speech_options import SpeechPronunciation


def apply_pronunciations(text: str, entries: list[SpeechPronunciation]) -> str:
    active = sorted((entry for entry in entries if entry.enabled), key=lambda entry: len(entry.word), reverse=True)
    if not active:
        return text
    alternatives = []
    for index, entry in enumerate(active):
        literal = re.escape(entry.word)
        if not entry.case_sensitive:
            literal = f"(?i:{literal})"
        alternatives.append(r"(?<!\w)(?P<p" + str(index) + ">" + literal + r")(?!\w)")
    pattern = re.compile("|".join(alternatives))
    return pattern.sub(lambda match: active[int(match.lastgroup[1:])].pronunciation, text)


_MONTHS = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
_UNITS = {
    "%": ("Prozent", "Prozent"), "€": ("Euro", "Euro"), "EUR": ("Euro", "Euro"),
    "$": ("Dollar", "Dollar"), "USD": ("Dollar", "Dollar"),
    "°C": ("Grad Celsius", "Grad Celsius"), "°F": ("Grad Fahrenheit", "Grad Fahrenheit"),
    "km": ("Kilometer", "Kilometer"), "cm": ("Zentimeter", "Zentimeter"),
    "mm": ("Millimeter", "Millimeter"), "m": ("Meter", "Meter"),
    "kg": ("Kilogramm", "Kilogramm"), "mg": ("Milligramm", "Milligramm"), "g": ("Gramm", "Gramm"),
    "ms": ("Millisekunde", "Millisekunden"), "s": ("Sekunde", "Sekunden"),
    "min": ("Minute", "Minuten"), "h": ("Stunde", "Stunden"),
    "kWh": ("Kilowattstunde", "Kilowattstunden"), "kW": ("Kilowatt", "Kilowatt"), "W": ("Watt", "Watt"),
    "GB": ("Gigabyte", "Gigabyte"), "MB": ("Megabyte", "Megabyte"),
    "GHz": ("Gigahertz", "Gigahertz"), "MHz": ("Megahertz", "Megahertz"),
    "kHz": ("Kilohertz", "Kilohertz"), "Hz": ("Hertz", "Hertz"),
}
_NUMBER = r"[+-]?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[,.]\d+)?)"
_UNIT_PATTERN = re.compile(r"(?<![\w.,])(" + _NUMBER + r")\s*(" + "|".join(re.escape(unit) for unit in sorted(_UNITS, key=len, reverse=True)) + r")(?!\w)")


def normalize_german_numbers(text: str) -> str:
    from num2words import num2words

    protected = []

    def protect(value: str) -> str:
        # No digits in placeholders: the later cardinal-number pass skips them.
        protected.append(value)
        index = len(protected) - 1
        label = ""
        while True:
            label = chr(65 + index % 26) + label
            index = index // 26 - 1
            if index < 0:
                break
        return "\ue000" + label + "\ue001"

    def integer(value: int) -> str:
        return str(num2words(value, lang="de"))

    def number(value: str, *, noun: bool = False) -> str:
        if len(value) > 24:
            return value
        value = value.replace("+", "")
        if "," in value:
            value = value.replace(".", "")
            whole, fraction = value.split(",", 1)
        elif "." in value:
            if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value):
                whole, fraction = value.replace(".", ""), ""
            else:
                whole, fraction = value.split(".", 1)
        else:
            whole, fraction = value, ""
        negative = whole.startswith("-")
        whole_number = int(whole)
        spoken = "ein" if noun and whole_number == 1 and not fraction else integer(abs(whole_number))
        if negative:
            spoken = "minus " + spoken
        if fraction:
            spoken += " Komma " + " ".join(integer(int(digit)) for digit in fraction)
        return spoken

    # Keep URLs, mail addresses and machine identifiers intact.
    text = re.sub(r"(?:https?://|www\.)[^\s<>]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", lambda match: protect(match.group()), text)
    text = re.sub(r"\b[A-Za-zÄÖÜäöü_][\w-]*\d[\w-]*\b", lambda match: protect(match.group()), text)

    def spoken_date(match: re.Match[str]) -> str:
        day, month, year = map(int, match.groups())
        try:
            date(year, month, day)
        except ValueError:
            return protect(match.group())
        ordinal = str(num2words(day, lang="de", to="ordinal"))
        before = match.string[max(0, match.start() - 12):match.start()]
        ending = "n" if re.search(r"\b(?:am|vom|zum|dem|den|des)\s*$", before, re.IGNORECASE) else ("" if re.search(r"\bder\s*$", before, re.IGNORECASE) else "r")
        return protect(f"{ordinal}{ending} {_MONTHS[month]} {integer(year)}")

    text = re.sub(r"(?<![\w.])(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\w|\.\d)", spoken_date, text)

    def spoken_time(match: re.Match[str]) -> str:
        hour, minute = int(match[1]), int(match[2])
        if hour > 23 or minute > 59:
            return protect(match.group())
        spoken_hour = "ein" if hour == 1 else integer(hour)
        return protect(f"{spoken_hour} Uhr" + (f" {integer(minute)}" if minute else ""))

    text = re.sub(r"(?<![\w:])(\d{1,2}):(\d{2})(?:\s*Uhr\b)?(?!\w|:\d)", spoken_time, text)

    def spoken_unit(match: re.Match[str]) -> str:
        value, unit = match.groups()
        if len(value) > 24:
            return protect(match.group())
        decimal_value = Decimal(value.replace(".", "").replace(",", ".")) if "," in value else Decimal(value.replace(".", "") if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value) else value)
        noun = _UNITS[unit][0 if decimal_value == 1 else 1]
        if unit in {"€", "EUR", "$", "USD"} and "," in value and len(value.split(",")[1]) == 2:
            whole = int(abs(decimal_value))
            cents = int((abs(decimal_value) - whole) * 100)
            spoken = ("ein" if whole == 1 else integer(whole)) + " " + noun
            if cents:
                spoken += " und " + integer(cents) + " Cent"
            return protect(("minus " if decimal_value < 0 else "") + spoken)
        spoken = number(value, noun=True)
        if decimal_value == 1 and noun in {"Stunde", "Minute", "Sekunde", "Millisekunde", "Kilowattstunde"}:
            spoken = "eine"
        return protect(spoken + " " + noun)

    text = _UNIT_PATTERN.sub(spoken_unit, text)
    # Spoken ordinals must not become a new sentence boundary ("im 2. Semester").
    genders = {"Semester": "s", "Kapitel": "s", "Jahr": "s", "Mal": "s",
               "Absatz": "r", "Versuch": "r", "Tag": "r", "Monat": "r", "Schritt": "r",
               "Seite": "", "Woche": "", "Aufgabe": "", "Klasse": ""}
    genders.update({month: "r" for month in _MONTHS[1:]})
    def spoken_ordinal(match: re.Match[str]) -> str:
        value, noun = int(match[1]), match[2]
        if value == 0:
            return protect(match.group())
        before = match.string[max(0, match.start() - 16):match.start()]
        if re.search(r"\b(?:im|am|vom|zum|zur|beim|dem|den|des)\s*$", before, re.IGNORECASE):
            ending = "n"
        elif re.search(r"\b(?:der|die|das)\s*$", before, re.IGNORECASE):
            ending = ""
        else:
            ending = genders[noun]
        ordinal = str(num2words(value, lang="de", to="ordinal"))
        return protect(ordinal + ending + " " + noun)
    text = re.sub(r"(?<![\w.])(\d{1,3})\.\s+(" + "|".join(genders) + r")(?!\w)", spoken_ordinal, text)
    # Preserve other ambiguous ordinals for the native German pronunciation.
    text = re.sub(r"(?<![\w.])\d+\.(?=\s+[A-Za-zÄÖÜäöüß])", lambda match: protect(match.group()), text)
    # A dotted version is ambiguous without a label; leave it unchanged.
    text = re.sub(r"(?<!\w)\d+(?:\.\d+)+(?!\w)", lambda match: protect(match.group()), text)
    # Preserve leading zeros and long identifiers rather than inventing a quantity.
    text = re.sub(r"(?<!\w)(?:0\d+|\d{7,})(?!\w)", lambda match: protect(match.group()), text)
    text = re.sub(r"(?<![\w.,:/])[-+]?\d+(?:,\d+)?(?!\w|[.,:/]\d)", lambda match: number(match.group()), text)
    def restore(match):
        index = 0
        for letter in match[1]:
            index = index * 26 + ord(letter) - 64
        return protected[index - 1] if 0 < index <= len(protected) else match.group()

    return re.sub("\ue000([A-Z]+)\ue001", restore, text)
