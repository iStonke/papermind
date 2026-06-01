"""Mapping from a detected document type to a default category name.

Shared by the import staging flow and the on-demand document metadata
suggestion so both produce identical category guesses.
"""

DOC_TYPE_TO_CATEGORY: dict[str, str] = {
    "Rechnung": "Rechnungen",
    "Quittung": "Belege",
    "Mahnung": "Rechnungen",
    "Vertrag": "Verträge",
    "Kündigung": "Verträge",
    "Brief": "Briefe",
    "Bescheid": "Briefe",
    "Protokoll": "Briefe",
}


def map_doc_type_to_category(doc_type: str | None) -> str | None:
    """Return the default category for ``doc_type`` or ``None`` if unmapped."""
    return DOC_TYPE_TO_CATEGORY.get(str(doc_type or "").strip())
