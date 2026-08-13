"""Hybrid wiki retrieval and evidence materialization for chat."""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from typing import Any, Iterable

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.wiki import WikiClaim, WikiPage
from app.services.embeddings import EmbeddingService
from app.services.wiki_trust import WikiTrustValidator, compact_text

logger = logging.getLogger("papermind.wiki.search")
settings = get_settings()

_QUERY_STOP_TERMS = {
    "alle",
    "das",
    "dem",
    "den",
    "der",
    "die",
    "ein",
    "eine",
    "fur",
    "habe",
    "hat",
    "hoch",
    "ich",
    "ist",
    "lautet",
    "mir",
    "sind",
    "steht",
    "und",
    "wann",
    "war",
    "was",
    "welche",
    "welcher",
    "welches",
    "wie",
    "wo",
}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.10f}" for value in vector) + "]"


def _term_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-z0-9ß]", "", ascii_value).replace("ß", "ss")
    for suffix in ("ungen", "ern", "en", "er", "es", "e", "n", "s"):
        if len(cleaned) > len(suffix) + 4 and cleaned.endswith(suffix):
            return cleaned[: -len(suffix)]
    return cleaned


def _meaningful_terms(value: str) -> set[str]:
    terms = {_term_key(token) for token in re.findall(r"[\wÄÖÜäöüß-]+", str(value or ""), re.UNICODE)}
    return {term for term in terms if len(term) >= 3 and term not in _QUERY_STOP_TERMS}


def _text_relevance(query_terms: set[str], *values: str) -> float:
    if not query_terms:
        return 1.0
    candidate_terms = _meaningful_terms(" ".join(str(value or "") for value in values))
    return len(query_terms & candidate_terms) / len(query_terms)


class WikiSearchService:
    def __init__(self, db: Session, owner_id: uuid.UUID):
        self.db = db
        self.owner_id = owner_id
        self.validator = WikiTrustValidator(db, owner_id)

    def refresh_page_embeddings(self, page_ids: Iterable[uuid.UUID]) -> int:
        unique_ids = list(dict.fromkeys(page_ids))
        if not unique_ids:
            return 0
        pages = list(
            self.db.execute(
                select(WikiPage).where(
                    WikiPage.owner_id == self.owner_id,
                    WikiPage.id.in_(unique_ids),
                    WikiPage.current_revision_id.isnot(None),
                )
            ).scalars()
        )
        texts = [compact_text(f"{page.title}\n{page.search_text}", 12_000) for page in pages]
        pairs = [(page, value) for page, value in zip(pages, texts, strict=True) if value]
        if not pairs:
            return 0
        try:
            model, dim, vectors, _ = EmbeddingService(self.db, self.owner_id).embed_texts(
                [value for _, value in pairs]
            )
            if dim != settings.embed_dim:
                raise RuntimeError(f"wiki embedding dimension mismatch: expected {settings.embed_dim}, got {dim}")
        except Exception as exc:  # pragma: no cover - optional local AI runtime
            logger.warning("wiki embedding skipped pages=%s error=%s", len(pairs), exc)
            return 0

        try:
            with self.db.begin_nested():
                for (page, _), vector in zip(pairs, vectors, strict=True):
                    self.db.execute(
                        text(
                            """
                            INSERT INTO wiki_page_embeddings (
                                page_id, owner_id, revision_id, model, dim, embedding, updated_at
                            ) VALUES (
                                :page_id, :owner_id, :revision_id, :model, :dim,
                                CAST(:embedding AS vector), now()
                            )
                            ON CONFLICT (page_id) DO UPDATE
                            SET owner_id = EXCLUDED.owner_id,
                                revision_id = EXCLUDED.revision_id,
                                model = EXCLUDED.model,
                                dim = EXCLUDED.dim,
                                embedding = EXCLUDED.embedding,
                                updated_at = now()
                            """
                        ),
                        {
                            "page_id": page.id,
                            "owner_id": self.owner_id,
                            "revision_id": page.current_revision_id,
                            "model": model,
                            "dim": dim,
                            "embedding": _vector_literal(vector),
                        },
                    )
        except Exception as exc:  # pragma: no cover - schema/runtime mismatch
            logger.warning("wiki embedding persistence failed error=%s", exc)
            return 0
        return len(pairs)

    def search_pages(
        self,
        query: str,
        *,
        query_vector: list[float] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        normalized_query = compact_text(query, 1000)
        if not normalized_query:
            return []
        candidate_limit = max(8, min(int(limit) * 3, 60))
        scores: dict[uuid.UUID, float] = {}
        metadata: dict[uuid.UUID, dict[str, Any]] = {}
        fts_scores: dict[uuid.UUID, float] = {}
        vector_scores: dict[uuid.UUID, float] = {}

        try:
            fts_rows = self.db.execute(
                text(
                    """
                    WITH q AS (SELECT websearch_to_tsquery('german', :query) AS value)
                    SELECT p.id, p.title, p.kind, p.status, p.current_revision_id,
                           ts_rank_cd(p.search_vector, q.value) AS raw_score
                    FROM wiki_pages p, q
                    WHERE p.owner_id = :owner_id
                      AND p.status IN ('active', 'needs_review')
                      AND p.search_vector @@ q.value
                    ORDER BY raw_score DESC, p.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"query": normalized_query, "owner_id": self.owner_id, "limit": candidate_limit},
            ).mappings().all()
        except Exception as exc:  # pragma: no cover - malformed DB config fallback
            logger.debug("wiki fts query failed: %s", exc)
            fts_rows = []

        for rank, row in enumerate(fts_rows, start=1):
            page_id = row["id"]
            scores[page_id] = scores.get(page_id, 0.0) + 1.0 / (60.0 + rank)
            metadata[page_id] = dict(row)
            fts_scores[page_id] = float(row.get("raw_score") or 0.0)

        if query_vector:
            try:
                vector_rows = self.db.execute(
                    text(
                        """
                        SELECT p.id, p.title, p.kind, p.status, p.current_revision_id,
                               1 - (e.embedding <=> CAST(:query_vector AS vector)) AS raw_score
                        FROM wiki_page_embeddings e
                        JOIN wiki_pages p ON p.id = e.page_id
                        WHERE e.owner_id = :owner_id
                          AND p.status IN ('active', 'needs_review')
                        ORDER BY e.embedding <=> CAST(:query_vector AS vector)
                        LIMIT :limit
                        """
                    ),
                    {
                        "query_vector": _vector_literal(query_vector),
                        "owner_id": self.owner_id,
                        "limit": candidate_limit,
                    },
                ).mappings().all()
            except Exception as exc:  # pragma: no cover - optional embeddings
                logger.debug("wiki vector query failed: %s", exc)
                vector_rows = []
            for rank, row in enumerate(vector_rows, start=1):
                page_id = row["id"]
                scores[page_id] = scores.get(page_id, 0.0) + 1.0 / (60.0 + rank)
                metadata.setdefault(page_id, dict(row))
                vector_scores[page_id] = float(row.get("raw_score") or 0.0)

        if not scores:
            pattern = f"%{normalized_query}%"
            fallback = self.db.execute(
                select(WikiPage).where(
                    WikiPage.owner_id == self.owner_id,
                    WikiPage.status.in_(("active", "needs_review")),
                    (WikiPage.title.ilike(pattern) | WikiPage.search_text.ilike(pattern)),
                ).limit(candidate_limit)
            ).scalars()
            for rank, page in enumerate(fallback, start=1):
                scores[page.id] = 1.0 / (60.0 + rank)
                fts_scores[page.id] = 0.01
                metadata[page.id] = {
                    "id": page.id,
                    "title": page.title,
                    "kind": page.kind,
                    "status": page.status,
                    "current_revision_id": page.current_revision_id,
                }

        ordered = sorted(scores, key=scores.get, reverse=True)[: max(1, min(limit, 20))]
        return [
            {
                **metadata[page_id],
                "score": scores[page_id],
                "fts_score": fts_scores.get(page_id, 0.0),
                "vector_score": vector_scores.get(page_id, 0.0),
            }
            for page_id in ordered
        ]

    def context_for_chat(
        self,
        query: str,
        *,
        query_vector: list[float] | None = None,
        page_limit: int = 6,
        claim_limit: int = 24,
        max_chars: int = 5000,
    ) -> dict[str, Any]:
        selected_pages = self.search_pages(query, query_vector=query_vector, limit=page_limit)
        if selected_pages:
            best_vector_score = max(float(row.get("vector_score") or 0.0) for row in selected_pages)
            vector_floor = max(0.45, best_vector_score - 0.07)
            relevant_pages = [
                row
                for row in selected_pages
                if float(row.get("fts_score") or 0.0) > 0.0
                or float(row.get("vector_score") or 0.0) >= vector_floor
            ]
            selected_pages = relevant_pages or selected_pages[:1]
        selected_ids = [row["id"] for row in selected_pages]
        if not selected_ids:
            return {"text": "", "pages": [], "claims": [], "evidence_chunks": []}

        # Do not fan a matching topic page back out to every linked source page.
        # That former expansion made a single invoice question pull unrelated
        # invoices into the answer context.
        claim_page_ids = selected_ids
        claims = list(
            self.db.execute(
                select(WikiClaim)
                .where(
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.page_id.in_(claim_page_ids),
                    WikiClaim.status == "active",
                    WikiClaim.claim_type == "fact",
                )
                .options(selectinload(WikiClaim.evidence))
                .order_by(WikiClaim.valid_from.desc().nullslast(), WikiClaim.created_at.desc())
                .limit(max(1, min(claim_limit * 2, 100)))
            ).scalars().unique()
        )
        pages_by_id = {
            page.id: page
            for page in self.db.execute(
                select(WikiPage).where(WikiPage.owner_id == self.owner_id, WikiPage.id.in_(claim_page_ids))
            ).scalars()
        }
        page_rows_by_id = {row["id"]: row for row in selected_pages}
        best_page_vector = max(
            (float(row.get("vector_score") or 0.0) for row in selected_pages),
            default=0.0,
        )
        query_terms = _meaningful_terms(query)

        def claim_rank(claim: WikiClaim) -> tuple[float, float]:
            page = pages_by_id.get(claim.page_id)
            relevance = _text_relevance(
                query_terms,
                page.title if page else "",
                claim.text,
                *(evidence.quote for evidence in claim.evidence if evidence.support_role == "supports"),
            )
            page_row = page_rows_by_id.get(claim.page_id, {})
            page_vector = float(page_row.get("vector_score") or 0.0)
            page_relevance = page_vector / best_page_vector if best_page_vector > 0 else 0.0
            return relevance, page_relevance

        claims.sort(key=claim_rank, reverse=True)

        trace_claims: list[dict[str, Any]] = []
        evidence_chunks: list[dict[str, Any]] = []
        lines: list[str] = []
        used_chars = 0
        seen_claims: set[uuid.UUID] = set()
        seen_chunks: set[uuid.UUID] = set()
        for claim in claims:
            if claim.id in seen_claims:
                continue
            claim_relevance, page_relevance = claim_rank(claim)
            if query_terms and claim_relevance <= 0.0:
                continue
            valid_evidence: list[dict[str, Any]] = []
            for evidence in claim.evidence:
                if evidence.support_role != "supports":
                    continue
                document = self.db.get(Document, evidence.document_id)
                chunk = self.db.get(DocumentChunk, evidence.chunk_id)
                if not document or not chunk or not self.validator.evidence_row_is_current(evidence, document, chunk):
                    continue
                item = {
                    "evidence_id": str(evidence.id),
                    "document_id": str(document.id),
                    "document_title": compact_text(document.display_name or document.original_filename or "Dokument"),
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "page_from": chunk.page_from,
                    "page_to": chunk.page_to,
                    "quote": evidence.quote,
                    "chunk_content_hash": chunk.content_hash,
                }
                valid_evidence.append(item)
                if chunk.id not in seen_chunks:
                    seen_chunks.add(chunk.id)
                    evidence_score = min(0.82, 0.35 + (0.30 * claim_relevance) + (0.15 * page_relevance))
                    evidence_chunks.append(
                        {
                            "doc_id": document.id,
                            "chunk_id": chunk.id,
                            "chunk_index": chunk.chunk_index,
                            "page_from": chunk.page_from,
                            "page_to": chunk.page_to,
                            "chunk_type": chunk.chunk_type,
                            "score": evidence_score,
                            "text": chunk.text,
                            "document_title": item["document_title"],
                            "wiki_claim_ids": [str(claim.id)],
                            "evidence_ids": [str(evidence.id)],
                        }
                    )
                else:
                    existing_chunk = next(
                        (candidate for candidate in evidence_chunks if candidate.get("chunk_id") == chunk.id),
                        None,
                    )
                    if existing_chunk is not None:
                        existing_chunk["score"] = max(
                            float(existing_chunk.get("score") or 0.0),
                            min(0.82, 0.35 + (0.30 * claim_relevance) + (0.15 * page_relevance)),
                        )
                        existing_chunk["wiki_claim_ids"] = list(
                            dict.fromkeys([*(existing_chunk.get("wiki_claim_ids") or []), str(claim.id)])
                        )
                        existing_chunk["evidence_ids"] = list(
                            dict.fromkeys([*(existing_chunk.get("evidence_ids") or []), str(evidence.id)])
                        )
            if not valid_evidence:
                continue
            page = pages_by_id.get(claim.page_id)
            page_title = page.title if page else "Wissensseite"
            rendered = (
                f"[Wiki-Claim {claim.id} | Seite: {page_title} | Status: {claim.status}]\n"
                f"{claim.text}\n"
                + "\n".join(
                    f"Beleg: {item['document_title']}, Seite {item['page_from'] or '-'}: \"{item['quote']}\""
                    for item in valid_evidence[:2]
                )
            )
            if lines and used_chars + len(rendered) > max_chars:
                continue
            lines.append(rendered)
            used_chars += len(rendered)
            seen_claims.add(claim.id)
            trace_claims.append(
                {
                    "claim_id": str(claim.id),
                    "page_id": str(claim.page_id),
                    "page_title": page_title,
                    "revision_id": str(claim.revision_id),
                    "status": claim.status,
                    "text": claim.text,
                    "evidence": valid_evidence,
                }
            )
            if len(trace_claims) >= claim_limit:
                break

        trace_pages = [
            {
                "page_id": str(row["id"]),
                "title": row["title"],
                "kind": row["kind"],
                "status": row["status"],
                "revision_id": str(row["current_revision_id"]) if row.get("current_revision_id") else None,
                "score": round(float(row["score"]), 6),
            }
            for row in selected_pages
        ]
        return {
            "text": "\n\n---\n\n".join(lines),
            "pages": trace_pages,
            "claims": trace_claims,
            "evidence_chunks": evidence_chunks,
        }
