import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document

logger = logging.getLogger("papermind.dedupe")
settings = get_settings()

_MAX_UINT64 = (1 << 64) - 1
_MAX_INT64 = (1 << 63) - 1
_MIN_TEXT_LENGTH_FOR_SIMHASH = 40
_SHINGLE_SIZE = 5


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_signed_int64(value: int) -> int:
    value &= _MAX_UINT64
    if value <= _MAX_INT64:
        return value
    return value - (1 << 64)


def _to_unsigned_int64(value: int) -> int:
    return value & _MAX_UINT64


class DocumentDeduplicationService:
    def __init__(self, db: Session):
        self.db = db

    def normalize_text(self, text: str | None) -> str:
        raw = (text or "").lower()
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return ""
        tokens = [token for token in raw.split(" ") if len(token) >= 2]
        return " ".join(tokens)

    def compute_text_hash_sha256(self, normalized_text: str) -> str:
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    def _compute_simhash64_unsigned(self, normalized_text: str) -> int | None:
        tokens = normalized_text.split()
        if not tokens:
            return None

        if len(tokens) < _SHINGLE_SIZE:
            shingles = [" ".join(tokens)]
        else:
            shingles = [" ".join(tokens[idx : idx + _SHINGLE_SIZE]) for idx in range(len(tokens) - _SHINGLE_SIZE + 1)]

        if not shingles:
            return None

        bit_weights = [0] * 64
        for shingle in shingles:
            digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest()
            hash_value = int.from_bytes(digest, byteorder="big", signed=False)
            for bit_index in range(64):
                if (hash_value >> bit_index) & 1:
                    bit_weights[bit_index] += 1
                else:
                    bit_weights[bit_index] -= 1

        simhash = 0
        for bit_index, weight in enumerate(bit_weights):
            if weight >= 0:
                simhash |= 1 << bit_index
        return simhash & _MAX_UINT64

    def _extract_buckets(self, simhash_unsigned: int) -> tuple[int, int, int, int]:
        return (
            simhash_unsigned & 0xFFFF,
            (simhash_unsigned >> 16) & 0xFFFF,
            (simhash_unsigned >> 32) & 0xFFFF,
            (simhash_unsigned >> 48) & 0xFFFF,
        )

    def _hamming_distance(self, left_signed: int, right_signed: int) -> int:
        left_unsigned = _to_unsigned_int64(left_signed)
        right_unsigned = _to_unsigned_int64(right_signed)
        return int((left_unsigned ^ right_unsigned).bit_count())

    def _find_best_simhash_candidate(
        self,
        *,
        document_id: uuid.UUID,
        simhash_signed: int,
        buckets: tuple[int, int, int, int],
    ) -> tuple[uuid.UUID | None, int | None, int]:
        stmt = (
            select(Document.id, Document.text_simhash64)
            .where(
                Document.id != document_id,
                Document.text_simhash64.is_not(None),
                or_(
                    Document.simhash_bucket1 == buckets[0],
                    Document.simhash_bucket2 == buckets[1],
                    Document.simhash_bucket3 == buckets[2],
                    Document.simhash_bucket4 == buckets[3],
                ),
            )
            .limit(settings.dedupe_candidate_limit)
        )
        rows = self.db.execute(stmt).all()
        if not rows:
            return None, None, 0

        best_document_id: uuid.UUID | None = None
        best_distance: int | None = None
        for candidate_id, candidate_simhash in rows:
            if candidate_simhash is None:
                continue
            distance = self._hamming_distance(simhash_signed, int(candidate_simhash))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_document_id = candidate_id

        return best_document_id, best_distance, len(rows)

    def evaluate_document_text_duplicate(self, document: Document, text_content: str | None) -> None:
        normalized_text = self.normalize_text(text_content)
        document.duplicate_checked_at = _now_utc()

        if len(normalized_text) < _MIN_TEXT_LENGTH_FOR_SIMHASH:
            document.text_hash_sha256 = None
            document.text_simhash64 = None
            document.simhash_bucket1 = None
            document.simhash_bucket2 = None
            document.simhash_bucket3 = None
            document.simhash_bucket4 = None
            if document.duplicate_kind == "text":
                document.duplicate_of_doc_id = None
                document.duplicate_kind = None
                document.duplicate_score = None
            return

        text_hash = self.compute_text_hash_sha256(normalized_text)
        simhash_unsigned = self._compute_simhash64_unsigned(normalized_text)
        if simhash_unsigned is None:
            return

        simhash_signed = _to_signed_int64(simhash_unsigned)
        buckets = self._extract_buckets(simhash_unsigned)

        document.text_hash_sha256 = text_hash
        document.text_simhash64 = simhash_signed
        document.simhash_bucket1 = buckets[0]
        document.simhash_bucket2 = buckets[1]
        document.simhash_bucket3 = buckets[2]
        document.simhash_bucket4 = buckets[3]

        best_candidate_id, best_distance, candidate_count = self._find_best_simhash_candidate(
            document_id=document.id,
            simhash_signed=simhash_signed,
            buckets=buckets,
        )

        if best_candidate_id is not None and best_distance is not None and best_distance <= settings.dedupe_text_distance_threshold:
            score = max(0.0, 1.0 - (best_distance / 64.0))
            document.duplicate_of_doc_id = best_candidate_id
            document.duplicate_kind = "text"
            document.duplicate_score = score
            logger.info(
                "duplicate_text_check doc_id=%s candidates_n=%s best_id=%s best_distance=%s score=%.4f",
                document.id,
                candidate_count,
                best_candidate_id,
                best_distance,
                score,
            )
            return

        if document.duplicate_kind == "text":
            document.duplicate_of_doc_id = None
            document.duplicate_kind = None
            document.duplicate_score = None

        logger.info(
            "duplicate_text_check doc_id=%s candidates_n=%s best_id=%s best_distance=%s score=%s",
            document.id,
            candidate_count,
            best_candidate_id,
            best_distance,
            None,
        )
