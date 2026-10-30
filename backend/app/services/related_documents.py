"""Explainable recommendations using owner-scoped metadata and document titles."""
from __future__ import annotations

import heapq
import math
import re
import unicodedata
import uuid

from sqlalchemy import case, false, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.documents import RelatedDocumentListResponse, RelatedDocumentMode, RelatedDocumentRead
from app.schemas.related_preferences import RelatedPreferences

_STOP_WORDS = set("der die das den dem des ein eine einer einem einen und oder von vom fuer fur im in am an auf zum zur mit ohne the of for and a to".split())
_MONTHS = set("januar januar jan februar feb maerz marz march mar april apr mai may juni june jun juli july jul august aug september sep sept oktober october okt oct november nov dezember december dez dec".split())
_GENERIC = set("rechnung beitragsrechnung beitrag beleg vertrag bescheid nachweis dokument datei scan kopie quelle unterlagen invoice document receipt".split())


def _title_parts(value: str) -> tuple[tuple[str, ...], frozenset[str]]:
    value = re.sub(r"\.[A-Za-z][A-Za-z0-9]{0,7}$", "", (value or "").strip()).casefold()
    for original, replacement in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        value = value.replace(original, replacement)
    value = "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
    tokens = tuple(token for token in re.findall(r"[a-z]+|\d+", value)
                   if token not in _STOP_WORDS and token not in _MONTHS
                   and (not token.isdigit() or (len(token) >= 3 and not 1900 <= int(token) <= 2099)))
    meaningful = frozenset(token for token in tokens if token not in _GENERIC and len(token) >= 3)
    return tokens, meaningful


def _title_similarity(source, candidate) -> tuple[float, bool]:
    source_tokens, source_terms = source
    tokens, terms = candidate
    if not source_terms or not terms:
        return 0.0, False
    identical = source_tokens == tokens
    overlap = source_terms & terms
    similarity = len(overlap) / len(source_terms | terms)
    # A broad single word or a year alone must never create a title match.
    if identical or (len(overlap) >= 2 and similarity >= .5):
        return similarity, identical
    return 0.0, False


def _searchable_title():
    title = func.lower(func.coalesce(func.nullif(func.trim(Document.display_name), ""), Document.original_filename))
    # Keep title candidate lookup portable between PostgreSQL and SQLite.
    for original, replacement in (("Ä", "ae"), ("ä", "ae"), ("Ö", "oe"), ("ö", "oe"), ("Ü", "ue"), ("ü", "ue"), ("ß", "ss")):
        title = func.replace(title, original, replacement)
    return title


class RelatedDocumentService:
    def __init__(self, db: Session, owner_id: uuid.UUID) -> None:
        self.db = db
        self.owner_id = owner_id

    def list(self, document_id: uuid.UUID, limit: int = 5, offset: int = 0,
             mode: RelatedDocumentMode = RelatedDocumentMode.recommended,
             preferences: RelatedPreferences | None = None) -> RelatedDocumentListResponse:
        mode = RelatedDocumentMode(mode)
        factors = (preferences or RelatedPreferences()).factors()
        limit, offset = max(1, min(limit, 20)), max(0, min(offset, 10000))
        source = self.db.execute(select(
            Document.id, Document.original_filename, Document.display_name, Document.document_type,
            Document.correspondent_id, Document.document_date,
        ).where(Document.id == document_id, Document.owner_id == self.owner_id,
                Document.is_deleted.is_(False))).one_or_none()
        if source is None:
            raise NotFoundError("Document not found")
        source_tags = self.db.execute(select(Tag.id, Tag.name).join(
            document_tags, document_tags.c.tag_id == Tag.id,
        ).where(document_tags.c.document_id == document_id, Tag.owner_id == self.owner_id)).all()
        tag_ids = [tag.id for tag in source_tags]
        source_title = _title_parts((source.display_name or "").strip() or source.original_filename)
        if mode == RelatedDocumentMode.correspondent and source.correspondent_id is None:
            return RelatedDocumentListResponse()
        if mode == RelatedDocumentMode.tags and not tag_ids:
            return RelatedDocumentListResponse()
        if not tag_ids and source.correspondent_id is None and not source_title[1]:
            return RelatedDocumentListResponse()

        weights: dict[uuid.UUID, float] = {}
        if tag_ids:
            document_count = self.db.scalar(select(func.count()).select_from(Document).where(
                Document.owner_id == self.owner_id, Document.is_deleted.is_(False))) or 0
            frequencies = self.db.execute(select(document_tags.c.tag_id, func.count()).join(
                Document, Document.id == document_tags.c.document_id,
            ).where(document_tags.c.tag_id.in_(tag_ids), Document.owner_id == self.owner_id,
                    Document.is_deleted.is_(False)).group_by(document_tags.c.tag_id)).all()
            weights = {tag_id: 1 + math.log((document_count + 1) / (count + 1)) for tag_id, count in frequencies}
        weighted_tag = case(*[(document_tags.c.tag_id == tag_id, weight) for tag_id, weight in weights.items()], else_=0.0) if weights else 0.0
        matches = select(
            document_tags.c.document_id, func.count().label("shared_count"),
            func.sum(weighted_tag).label("shared_weight"),
        ).where(document_tags.c.tag_id.in_(tag_ids)).group_by(document_tags.c.document_id).subquery()
        tag_counts = select(document_tags.c.document_id, func.count().label("tag_count")).join(
            Tag, Tag.id == document_tags.c.tag_id,
        ).where(Tag.owner_id == self.owner_id).group_by(document_tags.c.document_id).subquery()
        shared = func.coalesce(matches.c.shared_count, 0)
        same_correspondent = Document.correspondent_id == source.correspondent_id if source.correspondent_id else false()
        source_type = (source.document_type or "").strip().lower()
        same_type = func.lower(func.trim(Document.document_type)) == source_type if source_type else false()
        if mode == RelatedDocumentMode.correspondent:
            eligible = same_correspondent
        elif mode == RelatedDocumentMode.tags:
            eligible = shared > 0
        else:
            # Stream candidate metadata instead of loading the whole library or
            # truncating before ranking; older series members remain discoverable.
            title = _searchable_title()
            title_matches = [title.contains(term, autoescape=True) for term in sorted(source_title[1], key=lambda term: (-len(term), term))[:8]]
            eligible = or_(same_correspondent, shared > 0, *title_matches)
        query = select(
            Document.id, Document.original_filename, Document.display_name, Document.document_date,
            Document.created_at, Document.correspondent_id,
            same_correspondent.label("same_correspondent"), same_type.label("same_type"),
            shared.label("shared_tag_count"), func.coalesce(matches.c.shared_weight, 0).label("shared_weight"),
            func.coalesce(tag_counts.c.tag_count, 0).label("tag_count"),
        ).outerjoin(matches, matches.c.document_id == Document.id).outerjoin(
            tag_counts, tag_counts.c.document_id == Document.id,
        ).where(Document.owner_id == self.owner_id, Document.is_deleted.is_(False),
                Document.id != document_id, eligible)
        total = 0

        def ranked():
            nonlocal total
            for row in self.db.execute(query).yield_per(250):
                shared_count = int(row.shared_tag_count)
                overlap = shared_count / max(1, len(tag_ids) + row.tag_count - shared_count)
                rarity = float(row.shared_weight) / max(1, shared_count)
                coverage_factor = 1 if shared_count >= 2 else min(1, max(0, (rarity - 1) / 1.5))
                tag_score = min(16, 2 * float(row.shared_weight) + 4 * overlap * coverage_factor)
                title_score, identical_title = _title_similarity(source_title, _title_parts((row.display_name or "").strip() or row.original_filename))
                different_sender = bool(source.correspondent_id and row.correspondent_id and not row.same_correspondent)
                series = identical_title and not different_sender and bool(row.same_correspondent or row.same_type or shared_count)
                score = (4 * bool(row.same_correspondent) * factors['correspondent'] + bool(row.same_type) * factors['type']
                         + 3 * bool(row.same_correspondent and row.same_type) * min(factors['correspondent'], factors['type'])
                         + tag_score * factors['tags'] + (14 * factors['series'] if series else 8 * title_score * factors['title']))
                if mode == RelatedDocumentMode.recommended and score < 6:
                    continue
                total += 1
                distance = abs((row.document_date - source.document_date).days) if row.document_date and source.document_date else 10**9
                order = (-round(score, 6), distance, -(row.document_date.toordinal() if row.document_date else 0),
                         -(row.created_at.timestamp() if row.created_at else 0), str(row.id))
                yield order, row, bool(series), bool(title_score and not series)

        # Memory is bounded by the requested page even for a broad sender/tag.
        page = heapq.nsmallest(offset + limit, ranked(), key=lambda entry: entry[0])[offset:]
        names: dict[uuid.UUID, list[str]] = {entry[1].id: [] for entry in page}
        if names and tag_ids:
            shared_names = self.db.execute(select(document_tags.c.document_id, Tag.id, Tag.name).join(
                Tag, Tag.id == document_tags.c.tag_id,
            ).where(document_tags.c.document_id.in_(names), document_tags.c.tag_id.in_(tag_ids),
                    Tag.owner_id == self.owner_id)).all()
            shared_names.sort(key=lambda entry: (-weights.get(entry.id, 1), entry.name.casefold()))
            for doc_id, _tag_id, name in shared_names:
                if len(names[doc_id]) < 3:
                    names[doc_id].append(name)
        return RelatedDocumentListResponse(items=[RelatedDocumentRead(
            id=row.id, title=(row.display_name or "").strip() or row.original_filename,
            document_date=row.document_date, same_correspondent=bool(row.same_correspondent), same_type=bool(row.same_type),
            same_series=series, similar_title=similar_title,
            shared_tag_count=row.shared_tag_count, shared_tags=names[row.id],
        ) for _order, row, series, similar_title in page], total=total, has_more=offset + len(page) < total)
