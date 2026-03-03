def sanitize_text_for_db(value: str | None) -> str:
    """Remove characters that PostgreSQL text columns cannot store."""
    if not value:
        return ""
    return value.replace("\x00", "")

