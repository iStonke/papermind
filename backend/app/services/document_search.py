"""Reine Suchausdrücke und Eingabenormalisierung für Dokumentabfragen."""

from __future__ import annotations

import re

from sqlalchemy import false, func, or_, select

from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.documents import DocumentSearchScope


def normalize_search_query(value: str | None, *, max_length: int) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    return normalized[:max_length] if normalized else None


def build_ts_query_expr(normalized_query: str, fts_config: str):
    tokens = normalized_query.split()
    if not tokens:
        return func.websearch_to_tsquery(fts_config, normalized_query)
    safe_last = re.sub(r"[^\w\-]", "", tokens[-1], flags=re.UNICODE)
    if not safe_last:
        return func.websearch_to_tsquery(fts_config, normalized_query)
    prefix = func.to_tsquery(fts_config, safe_last + ":*")
    return prefix if len(tokens) == 1 else func.websearch_to_tsquery(fts_config, " ".join(tokens[:-1])).op("&&")(prefix)


def build_scoped_search_filter(normalized_query: str, search_scope: DocumentSearchScope):
    escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like_value = f"%{escaped}%"
    if search_scope == DocumentSearchScope.title:
        return or_(func.coalesce(Document.display_name, "").ilike(like_value, escape="\\"), Document.original_filename.ilike(like_value, escape="\\"))
    if search_scope == DocumentSearchScope.ocr_text:
        return func.coalesce(Document.text_content, "").ilike(like_value, escape="\\")
    if search_scope == DocumentSearchScope.document_type:
        return func.coalesce(Document.document_type, "").ilike(like_value, escape="\\")
    if search_scope == DocumentSearchScope.correspondent:
        return select(Correspondent.id).where(Correspondent.id == Document.correspondent_id, Correspondent.name.ilike(like_value, escape="\\")).exists()
    if search_scope == DocumentSearchScope.tags:
        return select(document_tags.c.document_id).join(Tag, Tag.id == document_tags.c.tag_id).where(document_tags.c.document_id == Document.id, Tag.name.ilike(like_value, escape="\\")).exists()
    if search_scope == DocumentSearchScope.year:
        year = int(normalized_query) if normalized_query.isdigit() and len(normalized_query) == 4 else None
        return false() if year is None else (Document.document_date.is_not(None) & (func.extract("year", Document.document_date) == year))
    return None
