import re

from sqlalchemy.exc import IntegrityError

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 30


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def validate_vocab_name(name: str, *, label: str = "Name") -> str:
    normalized = normalize_name(name)
    if len(normalized) < NAME_MIN_LENGTH:
        raise ValueError(f"{label} must contain at least {NAME_MIN_LENGTH} characters")
    if len(normalized) > NAME_MAX_LENGTH:
        raise ValueError(f"{label} must contain at most {NAME_MAX_LENGTH} characters")
    return normalized


def is_unique_violation(exc: IntegrityError, constraint_hint: str | None = None) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    if "duplicate key value violates unique constraint" not in message:
        return False
    if constraint_hint and constraint_hint.lower() not in message:
        return False
    return True
