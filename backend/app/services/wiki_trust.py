"""Deterministic validation for all durable wiki claims and evidence."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.wiki import WikiClaimEvidence
from app.schemas.wiki import WikiClaimCandidate, WikiClaimType


_STRUCTURED_SOURCE_PREDICATES = {
    "document_type",
    "document_date",
    "sender",
    "recipient",
    "amount",
}

_STRUCTURED_TEXT_PREFIXES = {
    "document_type": "Dokumenttyp",
    "sender": "Absender",
    "recipient": "Empfänger",
    "amount": "Betrag",
}


def compact_text(value: object | None, limit: int | None = None) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if limit is not None and len(normalized) > limit:
        return f"{normalized[:limit].rstrip()}…"
    return normalized


def normalized_evidence_text(value: object | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidatedEvidence:
    document: Document
    chunk: DocumentChunk
    quote: str
    quote_hash: str
    support_role: str
    start_offset: int | None
    end_offset: int | None


@dataclass(frozen=True)
class ClaimValidationResult:
    candidate: WikiClaimCandidate
    evidence: tuple[ValidatedEvidence, ...]
    errors: tuple[dict[str, str], ...]

    @property
    def valid_for_activation(self) -> bool:
        if self.errors:
            return False
        if self.candidate.claim_type == WikiClaimType.fact:
            return any(item.support_role == "supports" for item in self.evidence)
        return True


class WikiTrustValidator:
    def __init__(self, db: Session, owner_id: uuid.UUID):
        self.db = db
        self.owner_id = owner_id

    @staticmethod
    def _locate_quote(chunk_text: str, quote: str) -> tuple[int | None, int | None]:
        exact = str(chunk_text or "").casefold().find(str(quote or "").casefold())
        if exact >= 0:
            return exact, exact + len(quote)
        if normalized_evidence_text(quote) in normalized_evidence_text(chunk_text):
            # Whitespace/OCR normalization proves containment, but cannot safely
            # be mapped back to byte/character offsets.
            return None, None
        return -1, -1

    def validate_claim(self, candidate: WikiClaimCandidate) -> ClaimValidationResult:
        validated: list[ValidatedEvidence] = []
        errors: list[dict[str, str]] = []
        seen: set[tuple[uuid.UUID, str, str]] = set()

        for index, evidence in enumerate(candidate.evidence):
            document = self.db.execute(
                select(Document).where(
                    Document.id == evidence.document_id,
                    Document.owner_id == self.owner_id,
                )
            ).scalar_one_or_none()
            if document is None or document.is_deleted:
                errors.append({"field": f"evidence.{index}.document_id", "message": "source document is unavailable"})
                continue
            chunk = self.db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.id == evidence.chunk_id,
                    DocumentChunk.doc_id == document.id,
                )
            ).scalar_one_or_none()
            if chunk is None:
                errors.append({"field": f"evidence.{index}.chunk_id", "message": "chunk does not belong to source document"})
                continue

            start_offset, end_offset = self._locate_quote(chunk.text, evidence.quote)
            if start_offset == -1:
                errors.append({"field": f"evidence.{index}.quote", "message": "quote is not contained in the referenced chunk"})
                continue

            key = (chunk.id, sha256_text(evidence.quote), evidence.support_role.value)
            if key in seen:
                continue
            seen.add(key)
            validated.append(
                ValidatedEvidence(
                    document=document,
                    chunk=chunk,
                    quote=evidence.quote,
                    quote_hash=key[1],
                    support_role=evidence.support_role.value,
                    start_offset=start_offset,
                    end_offset=end_offset,
                )
            )

        if candidate.claim_type == WikiClaimType.fact and not any(
            item.support_role == "supports" for item in validated
        ):
            errors.append({"field": "evidence", "message": "a factual claim requires supporting source evidence"})
        elif candidate.claim_type == WikiClaimType.fact and not self.fact_is_source_supported(
            text=candidate.text,
            predicate=candidate.predicate,
            object_text=candidate.object_text,
            valid_from=candidate.valid_from,
            quotes=[item.quote for item in validated if item.support_role == "supports"],
        ):
            errors.append(
                {
                    "field": "text",
                    "message": "the factual statement is not an exact quote or a supported structured source value",
                }
            )

        return ClaimValidationResult(candidate=candidate, evidence=tuple(validated), errors=tuple(errors))

    @staticmethod
    def fact_is_source_supported(
        *,
        text: str,
        predicate: str | None,
        object_text: str | None,
        valid_from: date | None,
        quotes: list[str],
    ) -> bool:
        normalized_quotes = [normalized_evidence_text(value) for value in quotes if normalized_evidence_text(value)]
        normalized_text = normalized_evidence_text(text)
        if normalized_text and any(normalized_text in quote for quote in normalized_quotes):
            return True

        normalized_predicate = compact_text(predicate).lower()
        if normalized_predicate not in _STRUCTURED_SOURCE_PREDICATES:
            return False
        if normalized_predicate == "document_date" and valid_from:
            variants = (
                valid_from.isoformat(),
                valid_from.strftime("%d.%m.%Y"),
                valid_from.strftime("%d.%m.%y"),
            )
            normalized_variants = {normalized_evidence_text(value) for value in variants}
            canonical_texts = {
                normalized_evidence_text(f"Dokumentdatum: {valid_from.isoformat()}"),
                normalized_evidence_text(f"Dokumentdatum: {valid_from.strftime('%d.%m.%Y')}"),
            }
            return (
                normalized_evidence_text(object_text) in normalized_variants
                and normalized_text in canonical_texts
                and any(
                    normalized_evidence_text(variant) in quote
                    for variant in variants
                    for quote in normalized_quotes
                )
            )

        normalized_object = normalized_evidence_text(object_text)
        prefix = _STRUCTURED_TEXT_PREFIXES.get(normalized_predicate)
        canonical_text = normalized_evidence_text(f"{prefix}: {object_text}") if prefix and normalized_object else ""
        if not normalized_object or normalized_text != canonical_text:
            return False
        if any(normalized_object in quote for quote in normalized_quotes):
            return True
        if normalized_predicate == "amount":
            amount_match = re.search(r"\d[\d.]*[,.]\d{2}", normalized_object)
            if not amount_match:
                return False
            matching_quotes = [
                quote
                for quote in normalized_quotes
                if normalized_evidence_text(amount_match.group(0)) in quote
            ]
            if not matching_quotes:
                return False
            currency_text = re.sub(
                r"[\s.,:;_-]+",
                "",
                f"{normalized_object[:amount_match.start()]}{normalized_object[amount_match.end():]}",
            )
            if not currency_text:
                return True
            aliases = {
                "eur": {"eur", "€", "euro"},
                "€": {"eur", "€", "euro"},
                "euro": {"eur", "€", "euro"},
                "usd": {"usd", "$", "us-dollar"},
                "$": {"usd", "$", "us-dollar"},
                "usdollar": {"usd", "$", "us-dollar"},
                "gbp": {"gbp", "£", "pfund"},
                "£": {"gbp", "£", "pfund"},
                "pfund": {"gbp", "£", "pfund"},
            }.get(currency_text)
            if aliases is None:
                return False
            return any(any(alias in quote for alias in aliases) for quote in matching_quotes)
        return False

    @staticmethod
    def evidence_row_is_current(row: WikiClaimEvidence, document: Document, chunk: DocumentChunk) -> bool:
        if document.is_deleted or chunk.doc_id != document.id:
            return False
        if row.quote_hash != sha256_text(row.quote):
            return False
        if row.chunk_content_hash != chunk.content_hash:
            return False
        if row.document_text_hash and row.document_text_hash != document.text_hash:
            return False
        return normalized_evidence_text(row.quote) in normalized_evidence_text(chunk.text)
