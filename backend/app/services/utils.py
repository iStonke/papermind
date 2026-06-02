import re

from sqlalchemy.exc import IntegrityError

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 30

# Korrespondentennamen sind echte Organisations-/Personennamen und dürfen länger
# sein als das knappe Vokabular für Tags/Dokumenttypen.
CORRESPONDENT_NAME_MIN_LENGTH = 2
CORRESPONDENT_NAME_MAX_LENGTH = 120
CORRESPONDENT_ALIAS_MAX_LENGTH = 120


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def validate_vocab_name(name: str, *, label: str = "Name") -> str:
    normalized = normalize_name(name)
    if len(normalized) < NAME_MIN_LENGTH:
        raise ValueError(f"{label} must contain at least {NAME_MIN_LENGTH} characters")
    if len(normalized) > NAME_MAX_LENGTH:
        raise ValueError(f"{label} must contain at most {NAME_MAX_LENGTH} characters")
    return normalized


def validate_correspondent_name(name: str, *, label: str = "Correspondent name") -> str:
    normalized = normalize_name(name)
    if len(normalized) < CORRESPONDENT_NAME_MIN_LENGTH:
        raise ValueError(f"{label} must contain at least {CORRESPONDENT_NAME_MIN_LENGTH} characters")
    if len(normalized) > CORRESPONDENT_NAME_MAX_LENGTH:
        raise ValueError(f"{label} must contain at most {CORRESPONDENT_NAME_MAX_LENGTH} characters")
    return normalized


def validate_correspondent_alias(alias: str, *, label: str = "Alias") -> str:
    normalized = normalize_name(alias)
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if len(normalized) > CORRESPONDENT_ALIAS_MAX_LENGTH:
        raise ValueError(f"{label} must contain at most {CORRESPONDENT_ALIAS_MAX_LENGTH} characters")
    return normalized


def is_unique_violation(exc: IntegrityError, constraint_hint: str | None = None) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    if "duplicate key value violates unique constraint" not in message:
        return False
    if constraint_hint and constraint_hint.lower() not in message:
        return False
    return True
