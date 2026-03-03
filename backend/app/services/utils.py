import re

from sqlalchemy.exc import IntegrityError


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def is_unique_violation(exc: IntegrityError, constraint_hint: str | None = None) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    if "duplicate key value violates unique constraint" not in message:
        return False
    if constraint_hint and constraint_hint.lower() not in message:
        return False
    return True
