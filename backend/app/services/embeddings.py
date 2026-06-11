import hashlib
import logging
import math
import re
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, StorageError
from app.core.text import sanitize_text_for_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_file import DocumentFile
from app.services.deduplication import DocumentDeduplicationService
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.embeddings")
settings = get_settings()

_EMBED_INSERT_SQL = text(
    """
    INSERT INTO doc_embeddings (id, chunk_id, model, dim, embedding)
    VALUES (:id, :chunk_id, :model, :dim, CAST(:embedding AS vector))
    ON CONFLICT (chunk_id)
    DO UPDATE
    SET model = EXCLUDED.model,
        dim = EXCLUDED.dim,
        embedding = EXCLUDED.embedding,
        created_at = now()
    """
)

_INVOICE_LINE_PATTERN = re.compile(r"(€|\bEUR\b|\bMwSt\b|\bSumme\b|\bTotal\b)", re.IGNORECASE)
_INVOICE_TOTAL_PATTERN = re.compile(r"(Gesamtbetrag|Gesamtsumme|Endbetrag|Rechnungsbetrag|\bTotal\b|\bSumme\b)", re.IGNORECASE)
_IBAN_DE_PATTERN = re.compile(r"\bDE\d{2}[ ]?(?:\d{4}[ ]?){4}\d{2}\b", re.IGNORECASE)
_IBAN_GENERIC_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_BANK_LINE_PATTERN = re.compile(r"(\bIBAN\b|\bBIC\b|\bBank\b|\bBankverbindung\b|\bKontoinhaber\b|\bSEPA\b)", re.IGNORECASE)
_TABLE_LINE_PATTERN = re.compile(r"\|")
_TABLE_NUMERIC_PATTERN = re.compile(r"\d+[.,]?\d*")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(text_value: str) -> str:
    sanitized = sanitize_text_for_db(str(text_value or ""))
    lines = [line.strip() for line in sanitized.splitlines()]
    compact = "\n".join(line for line in lines if line)
    compact = re.sub(r"[ \t]+", " ", compact)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def _normalize_line(text_value: str) -> str:
    return " ".join(sanitize_text_for_db(str(text_value or "")).split()).strip()


def _sha256_text(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def _vector_to_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.10f}" for value in vector) + "]"


def _truncate_error(message: str, max_length: int = 3500) -> str:
    value = str(message or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def _build_invoice_line_chunks(page_lines: list[tuple[int, list[str]]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    for page_no, lines in page_lines:
        for idx, current_line in enumerate(lines):
            if not _INVOICE_LINE_PATTERN.search(current_line):
                continue

            from_idx = max(0, idx - 2)
            context_lines = lines[from_idx : idx + 1]
            text_value = " ".join(context_lines).strip()
            if not text_value:
                continue

            if len(text_value) > 300:
                text_value = text_value[-300:].lstrip()

            chunk_type = "invoice_total" if _INVOICE_TOTAL_PATTERN.search(current_line) else "invoice_table"
            content_hash = _sha256_text(f"{page_no}:{chunk_type}:{text_value}")
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            chunks.append(
                {
                    "text": text_value,
                    "char_len": len(text_value),
                    "page_from": page_no,
                    "page_to": page_no,
                    "chunk_type": chunk_type,
                }
            )

    return chunks


def _build_bank_pattern_chunks(page_lines: list[tuple[int, list[str]]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    for page_no, lines in page_lines:
        for idx, current_line in enumerate(lines):
            line_has_bank_hint = bool(_BANK_LINE_PATTERN.search(current_line))
            line_has_iban = bool(_IBAN_DE_PATTERN.search(current_line) or _IBAN_GENERIC_PATTERN.search(current_line))
            if not (line_has_bank_hint or line_has_iban):
                continue

            from_idx = max(0, idx - 2)
            to_idx = min(len(lines), idx + 3)
            context_lines = lines[from_idx:to_idx]
            text_value = " ".join(context_lines).strip()
            if not text_value:
                continue
            if len(text_value) > 300:
                text_value = text_value[:300].rstrip()

            content_hash = _sha256_text(f"{page_no}:bank_details:{text_value}")
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            chunks.append(
                {
                    "text": text_value,
                    "char_len": len(text_value),
                    "page_from": page_no,
                    "page_to": page_no,
                    "chunk_type": "bank_details",
                }
            )

    return chunks


def _split_chunks(
    full_text: str,
    page_ranges: list[tuple[int, int, int]],
    page_lines: list[tuple[int, list[str]]],
) -> list[dict[str, Any]]:
    chunk_size = max(200, settings.chunk_size_chars)
    overlap = max(0, min(settings.chunk_overlap_chars, chunk_size // 2))
    text_len = len(full_text)
    if text_len == 0:
        return _build_invoice_line_chunks(page_lines)

    def choose_end(start: int) -> int:
        hard_end = min(start + chunk_size, text_len)
        if hard_end >= text_len:
            return text_len

        window = full_text[start:hard_end]
        min_cut = int(len(window) * 0.6)
        separators = ["\n\n", ". ", "! ", "? ", "; ", ", ", " "]
        candidate = -1
        for separator in separators:
            idx = window.rfind(separator)
            if idx >= min_cut:
                candidate = max(candidate, idx + len(separator))
        if candidate > 0:
            return start + candidate
        return hard_end

    chunks: list[dict[str, Any]] = []
    start = 0
    guard = 0
    while start < text_len and guard < 20000:
        guard += 1
        end = choose_end(start)
        if end <= start:
            end = min(start + chunk_size, text_len)
        raw_chunk = full_text[start:end].strip()
        if not raw_chunk:
            if end >= text_len:
                break
            start = max(end - overlap, start + 1)
            continue

        overlapping_pages = [page_no for page_no, p_start, p_end in page_ranges if p_start < end and p_end > start]
        chunks.append(
            {
                "text": raw_chunk,
                "char_len": len(raw_chunk),
                "page_from": min(overlapping_pages) if overlapping_pages else None,
                "page_to": max(overlapping_pages) if overlapping_pages else None,
                "chunk_type": "header",
            }
        )

        if end >= text_len:
            break
        start = max(end - overlap, start + 1)

    pattern_chunks = _build_invoice_line_chunks(page_lines) + _build_bank_pattern_chunks(page_lines)
    if pattern_chunks:
        existing_hashes = {_sha256_text(str(chunk["text"])) for chunk in chunks}
        for chunk in pattern_chunks:
            text_hash = _sha256_text(str(chunk["text"]))
            if text_hash in existing_hashes:
                continue
            existing_hashes.add(text_hash)
            chunks.append(chunk)

    return chunks


class EmbeddingService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _storage_root(self) -> Path:
        return Path(settings.storage_path).resolve()

    def _resolve_storage_path(self, file_key: str) -> Path:
        storage_root = self._storage_root()
        candidate = (storage_root / file_key).resolve()
        if storage_root != candidate and storage_root not in candidate.parents:
            raise StorageError("Invalid storage path")
        return candidate

    def _select_source_file(self, document: Document) -> DocumentFile:
        by_role = {record.role: record for record in document.files}
        source = by_role.get("ocr") or by_role.get("original")
        if source is None:
            raise NotFoundError(
                "No source PDF is available for indexing",
                details={"document_id": str(document.id)},
            )
        return source

    def _extract_page_texts(
        self, file_path: Path
    ) -> tuple[str, list[tuple[int, int, int]], bool, list[tuple[int, list[str]]]]:
        if not file_path.exists() or not file_path.is_file():
            raise NotFoundError("Source PDF is missing in storage", details={"path": str(file_path)})

        reader = PdfReader(str(file_path))
        text_parts: list[str] = []
        page_ranges: list[tuple[int, int, int]] = []
        page_lines: list[tuple[int, list[str]]] = []
        cursor = 0

        for page_index, page in enumerate(reader.pages):
            raw_text = sanitize_text_for_db(page.extract_text() or "")
            lines = [_normalize_line(line) for line in raw_text.splitlines()]
            lines = [line for line in lines if line]
            if not lines:
                continue

            extracted = _normalize_text(" ".join(lines))
            if not extracted:
                continue

            page_no = page_index + 1
            page_lines.append((page_no, lines))

            if text_parts:
                text_parts.append("\n\n")
                cursor += 2

            start = cursor
            text_parts.append(extracted)
            cursor += len(extracted)
            end = cursor
            page_ranges.append((page_no, start, end))

        full_text = "".join(text_parts).strip()
        return full_text, page_ranges, bool(page_ranges), page_lines

    def _embed_text_batch(self, texts: list[str], model_name: str) -> tuple[str, int, list[list[float]], float]:
        payload = {"model": model_name, "texts": texts}
        start = time.perf_counter()
        response = httpx.post(
            f"{settings.ai_base_url.rstrip('/')}/embed",
            json=payload,
            timeout=settings.ai_embed_timeout_seconds,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        data = response.json()
        vectors = data.get("vectors") or []
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding API returned an unexpected vector count")
        model = str(data.get("model") or model_name).strip() or model_name
        dim = int(data.get("dim") or 0)
        if dim <= 0:
            raise RuntimeError("Embedding API returned an invalid vector dimension")
        return model, dim, vectors, elapsed_ms

    def get_document_for_indexing(self, document_id: uuid.UUID) -> Document:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.files))
        )
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        document = self.db.execute(stmt).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        return document

    def index_document(self, document_id: uuid.UUID, *, force: bool = False) -> dict[str, Any]:
        document = self.get_document_for_indexing(document_id)
        dedupe_service = DocumentDeduplicationService(self.db)
        source_file = self._select_source_file(document)
        source_path = self._resolve_storage_path(source_file.file_key)

        extraction_start = time.perf_counter()
        full_text, page_ranges, page_refs_present, page_lines = self._extract_page_texts(source_path)
        extract_ms = (time.perf_counter() - extraction_start) * 1000
        if not full_text:
            raise BadRequestError(
                "Document has no extractable text for indexing",
                details={"document_id": str(document_id)},
            )

        text_hash = _sha256_text(full_text)
        if not force and document.text_hash == text_hash and document.embedding_status == "done":
            existing_chunk_count = self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(DocumentChunk.doc_id == document_id)
            ) or 0
            logger.info(
                "embedding skipped document_id=%s reason=hash_unchanged chunk_count=%s",
                document_id,
                existing_chunk_count,
            )
            return {
                "skipped": True,
                "document_id": str(document_id),
                "chunk_count": int(existing_chunk_count),
                "text_hash": text_hash,
            }

        chunking_start = time.perf_counter()
        chunks = _split_chunks(full_text, page_ranges, page_lines)
        chunking_ms = (time.perf_counter() - chunking_start) * 1000
        if not chunks:
            raise BadRequestError(
                "Chunking produced no chunks",
                details={"document_id": str(document_id)},
            )

        delete_start = time.perf_counter()
        self.db.execute(
            text(
                """
                DELETE FROM doc_embeddings
                WHERE chunk_id IN (SELECT id FROM doc_chunks WHERE doc_id = :doc_id)
                """
            ),
            {"doc_id": document_id},
        )
        self.db.execute(text("DELETE FROM doc_chunks WHERE doc_id = :doc_id"), {"doc_id": document_id})
        self.db.flush()
        delete_ms = (time.perf_counter() - delete_start) * 1000

        chunk_rows: list[DocumentChunk] = []
        for chunk in chunks:
            chunk_text = sanitize_text_for_db(str(chunk["text"]))
            if not chunk_text:
                continue
            chunk_rows.append(
                DocumentChunk(
                    doc_id=document_id,
                    chunk_index=len(chunk_rows),
                    page_from=chunk["page_from"],
                    page_to=chunk["page_to"],
                    chunk_type=str(chunk.get("chunk_type") or "header"),
                    text=chunk_text,
                    char_len=len(chunk_text),
                    token_len=None,
                    content_hash=_sha256_text(chunk_text),
                )
            )
        if not chunk_rows:
            raise BadRequestError(
                "Chunking produced no chunks",
                details={"document_id": str(document_id)},
            )
        self.db.add_all(chunk_rows)
        self.db.flush()

        model_name = settings.embed_model
        embed_batch_size = max(1, settings.embed_batch_size)
        total_embed_ms = 0.0
        model_used = model_name
        dim_used = 0
        embedding_rows: list[dict[str, Any]] = []
        batches = math.ceil(len(chunk_rows) / embed_batch_size)

        for batch_index in range(batches):
            start_idx = batch_index * embed_batch_size
            end_idx = min(len(chunk_rows), start_idx + embed_batch_size)
            batch_chunks = chunk_rows[start_idx:end_idx]
            batch_texts = [chunk.text for chunk in batch_chunks]
            batch_model, batch_dim, vectors, elapsed_ms = self._embed_text_batch(batch_texts, model_name)
            total_embed_ms += elapsed_ms

            if dim_used == 0:
                dim_used = batch_dim
                model_used = batch_model
            elif dim_used != batch_dim:
                raise RuntimeError(
                    f"Embedding API dimension changed across batches ({dim_used} -> {batch_dim})"
                )

            if batch_dim != settings.embed_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch, expected {settings.embed_dim} got {batch_dim}"
                )

            for chunk_row, vector in zip(batch_chunks, vectors, strict=True):
                embedding_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "chunk_id": chunk_row.id,
                        "model": model_used,
                        "dim": dim_used,
                        "embedding": _vector_to_literal(vector),
                    }
                )

        upsert_start = time.perf_counter()
        if embedding_rows:
            self.db.execute(_EMBED_INSERT_SQL, embedding_rows)
        upsert_ms = (time.perf_counter() - upsert_start) * 1000

        document.text_content = sanitize_text_for_db(full_text)
        document.text_hash = text_hash
        document.embedding_status = "done"
        document.embedding_model = model_used
        document.embedding_dim = dim_used
        document.embedding_error = None
        document.embedding_updated_at = _now_utc()
        try:
            dedupe_service.evaluate_document_text_duplicate(document, full_text)
        except Exception as exc:  # pragma: no cover - best effort dedupe
            logger.warning("duplicate_text_check_failed document_id=%s error=%s", document_id, exc)

        if source_file.role == "ocr":
            document.text_source = "ocr"
        elif document.text_source == "none":
            document.text_source = "embedded"

        self.db.commit()

        avg_chars = int(sum(chunk.char_len for chunk in chunk_rows) / len(chunk_rows))
        logger.info(
            "chunking completed document_id=%s chunk_count=%s avg_chars=%s page_refs_present=%s extract_ms=%.2f chunk_ms=%.2f",
            document_id,
            len(chunk_rows),
            avg_chars,
            page_refs_present,
            extract_ms,
            chunking_ms,
        )
        logger.info(
            "embedding completed document_id=%s model=%s dim=%s n_chunks=%s batches=%s embed_time_ms=%.2f upsert_time_ms=%.2f delete_time_ms=%.2f",
            document_id,
            model_used,
            dim_used,
            len(chunk_rows),
            batches,
            total_embed_ms,
            upsert_ms,
            delete_ms,
        )

        return {
            "skipped": False,
            "document_id": str(document_id),
            "chunk_count": len(chunk_rows),
            "embedding_dim": dim_used,
            "embedding_model": model_used,
            "extract_ms": round(extract_ms, 2),
            "chunking_ms": round(chunking_ms, 2),
            "embed_ms": round(total_embed_ms, 2),
            "upsert_ms": round(upsert_ms, 2),
            "text_hash": text_hash,
        }

    def list_document_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        self.get_document_for_indexing(document_id)
        return self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars().all()

    def get_embedding_status(self, document_id: uuid.UUID) -> dict[str, Any]:
        document = self.db.get(Document, document_id)
        if document is None or (self.owner_id is not None and document.owner_id != self.owner_id):
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})

        chunk_count = self.db.scalar(
            select(func.count()).select_from(DocumentChunk).where(DocumentChunk.doc_id == document_id)
        ) or 0
        embedded_count = self.db.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM doc_embeddings e
                JOIN doc_chunks c ON c.id = e.chunk_id
                WHERE c.doc_id = :doc_id
                """
            ),
            {"doc_id": document_id},
        ) or 0

        return {
            "document_id": str(document_id),
            "embedding_status": document.embedding_status,
            "chunk_count": int(chunk_count),
            "embedded_count": int(embedded_count),
            "model": document.embedding_model,
            "dim": document.embedding_dim,
            "text_hash": document.text_hash,
            "updated_at": document.embedding_updated_at,
            "last_error": document.embedding_error,
        }

    def retrieve(
        self,
        query: str,
        top_k: int,
        doc_id: uuid.UUID | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        normalized_query = " ".join((query or "").split()).strip()
        if not normalized_query:
            raise BadRequestError("query must not be empty")

        top_k_value = max(1, min(top_k, settings.retrieval_max_top_k))
        embed_start = time.perf_counter()
        model_used, dim_used, vectors, _ = self._embed_text_batch([normalized_query], settings.embed_model)
        embed_ms = (time.perf_counter() - embed_start) * 1000
        query_vector = _vector_to_literal(vectors[0])

        sql_parts = [
            """
            SELECT
                c.doc_id,
                c.id AS chunk_id,
                c.chunk_index,
                c.page_from,
                c.page_to,
                c.chunk_type,
                c.text,
                1 - (e.embedding <=> CAST(:query_vector AS vector)) AS score
            FROM doc_embeddings e
            JOIN doc_chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = c.doc_id
            WHERE 1=1
            """
        ]
        params: dict[str, Any] = {"query_vector": query_vector, "top_k": top_k_value}

        if self.owner_id is not None:
            sql_parts.append(" AND d.owner_id = :owner_id")
            params["owner_id"] = self.owner_id
        if doc_id is not None:
            sql_parts.append(" AND c.doc_id = :doc_id")
            params["doc_id"] = doc_id
        if date_from is not None:
            sql_parts.append(" AND d.document_date >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            sql_parts.append(" AND d.document_date <= :date_to")
            params["date_to"] = date_to
        if tag_ids:
            placeholders = []
            for index, tag_id in enumerate(tag_ids):
                key = f"tag_id_{index}"
                placeholders.append(f"CAST(:{key} AS uuid)")
                params[key] = tag_id
            sql_parts.append(
                " AND EXISTS ("
                "SELECT 1 FROM document_tags dt "
                "WHERE dt.document_id = c.doc_id "
                f"AND dt.tag_id IN ({','.join(placeholders)})"
                ")"
            )

        sql_parts.append(" ORDER BY e.embedding <=> CAST(:query_vector AS vector)")
        sql_parts.append(" LIMIT :top_k")
        stmt = text("".join(sql_parts))

        db_start = time.perf_counter()
        # HNSW-Suchbreite für diese Transaktion setzen (muss >= top_k sein).
        ef_search = max(int(settings.hnsw_ef_search), top_k_value)
        self.db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
        rows = self.db.execute(stmt, params).mappings().all()
        db_ms = (time.perf_counter() - db_start) * 1000
        total_ms = embed_ms + db_ms

        results = []
        scores: list[float] = []
        for row in rows:
            score = float(row["score"]) if row["score"] is not None else 0.0
            scores.append(score)
            results.append(
                {
                    "doc_id": row["doc_id"],
                    "chunk_id": row["chunk_id"],
                    "chunk_index": row["chunk_index"],
                    "page_from": row["page_from"],
                    "page_to": row["page_to"],
                    "chunk_type": row["chunk_type"],
                    "score": score,
                    "text": row["text"],
                }
            )

        best_score = max(scores) if scores else None
        worst_score = min(scores) if scores else None
        logger.info(
            "retrieval query_len=%s top_k=%s embed_ms=%.2f db_ms=%.2f total_ms=%.2f best_score=%s worst_score=%s doc_ids=%s",
            len(normalized_query),
            top_k_value,
            embed_ms,
            db_ms,
            total_ms,
            best_score,
            worst_score,
            [str(item["doc_id"]) for item in results],
        )

        return {
            "query": normalized_query,
            "model": model_used,
            "dim": dim_used,
            "top_k": top_k_value,
            "results": results,
            "timings": {
                "embed_ms": round(embed_ms, 2),
                "db_ms": round(db_ms, 2),
                "total_ms": round(total_ms, 2),
            },
        }
