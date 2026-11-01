"""Resolve document corrections without changing the stored AI evidence."""
from typing import Any


def knowledge_value(document: Any, field: str) -> Any:
    manual = (getattr(document, "flags", None) or {}).get("manual_metadata_fields") or []
    value = getattr(document, field, None)
    if field in manual or value is not None:
        return value
    return getattr(document, f"ai_{field}", None)
