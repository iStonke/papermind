"""Source-grounded, versioned LLM-wiki operations.

The service deliberately separates proposal generation from publication.  It
only publishes factual claims after :class:`WikiTrustValidator` has proven that
their quote exists in a current, owner-scoped document chunk.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import and_, case, func, literal, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.chat import ChatMessage
from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.wiki import (
    WikiClaim,
    WikiClaimEvidence,
    WikiEvent,
    WikiLink,
    WikiPage,
    WikiPageRevision,
    WikiUpdateProposal,
)
from app.schemas.wiki import (
    WikiBackfillResponse,
    WikiCaptureAnswerRequest,
    WikiClaimCandidate,
    WikiClaimCorrectionRequest,
    WikiClaimRead,
    WikiClaimRetractRequest,
    WikiClaimStatus,
    WikiClaimType,
    WikiEvidenceCandidate,
    WikiEvidenceRead,
    WikiLintIssue,
    WikiLintResponse,
    WikiLinkRead,
    WikiOverviewResponse,
    WikiPageDetail,
    WikiPageKind,
    WikiPageListItem,
    WikiPageListResponse,
    WikiPageStatus,
    WikiProposalListResponse,
    WikiProposalRead,
    WikiProposalReviewRequest,
    WikiRevisionRead,
)
from app.services.chat_sessions import ChatSessionService
from app.services.settings import SettingsService
from app.services.wiki_extraction import WikiClaimExtractionService, WIKI_EXTRACTION_PROMPT_VERSION
from app.services.wiki_trust import (
    ClaimValidationResult,
    WikiTrustValidator,
    compact_text,
    normalized_evidence_text,
    sha256_text,
)

logger = logging.getLogger("papermind.wiki")

WIKI_SCHEMA_VERSION = "2"
WIKI_PROMPT_VERSION = "source-claims-v1"
AGGREGATE_RECENT_CLAIM_LIMIT = 40
_CONTRACT_MARKERS = ("vertrag", "police", "versicherung", "darlehen", "miete", "abonnement", "abo")
_ACTIVE_CLAIM_STATUSES = ("active", "disputed")


def _slugify(value: object | None, *, fallback: str = "wissen") -> str:
    normalized = normalized_evidence_text(value)
    normalized = (
        normalized.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug[:160] or fallback


def _title(document: Document) -> str:
    return compact_text(document.display_name or document.original_filename or "Dokument") or "Dokument"


def _format_amount(amount: Decimal | None, currency: str | None) -> str:
    if amount is None:
        return ""
    rendered = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{rendered} {compact_text(currency) or 'EUR'}"


def _amount_variants(amount: Decimal, currency: str | None) -> list[str]:
    plain_dot = f"{amount:.2f}"
    plain_comma = plain_dot.replace(".", ",")
    grouped = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    currency_value = compact_text(currency) or "EUR"
    return [
        f"{grouped} {currency_value}",
        f"{plain_comma} {currency_value}",
        f"{plain_comma} €",
        f"€ {plain_comma}",
        grouped,
        plain_comma,
        plain_dot,
    ]


def _date_variants(value: date) -> list[str]:
    return [value.strftime("%d.%m.%Y"), value.strftime("%d.%m.%y"), value.isoformat()]


def _quote_window(chunk_text: str, needle: str, *, radius: int = 110) -> str | None:
    haystack = str(chunk_text or "")
    position = haystack.casefold().find(str(needle or "").casefold())
    if position < 0:
        return None
    start = max(0, position - radius)
    end = min(len(haystack), position + len(needle) + radius)
    # Prefer natural line boundaries when they are close to the match.
    previous_break = haystack.rfind("\n", start, position)
    if previous_break >= 0:
        start = previous_break + 1
    next_break = haystack.find("\n", position + len(needle), end)
    if next_break >= 0:
        end = next_break
    return compact_text(haystack[start:end], 600) or None


class WikiService:
    def __init__(self, db: Session, owner_id: uuid.UUID):
        self.db = db
        self.owner_id = owner_id
        self.validator = WikiTrustValidator(db, owner_id)

    def _event(
        self,
        event_type: str,
        *,
        page_id: uuid.UUID | None = None,
        revision_id: uuid.UUID | None = None,
        claim_id: uuid.UUID | None = None,
        proposal_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WikiEvent:
        event = WikiEvent(
            owner_id=self.owner_id,
            event_type=event_type,
            page_id=page_id,
            revision_id=revision_id,
            claim_id=claim_id,
            proposal_id=proposal_id,
            payload=payload or {},
        )
        self.db.add(event)
        return event

    def _get_page(self, page_id: uuid.UUID, *, for_update: bool = False) -> WikiPage:
        stmt = select(WikiPage).where(WikiPage.id == page_id, WikiPage.owner_id == self.owner_id)
        if for_update:
            stmt = stmt.with_for_update()
        page = self.db.execute(stmt).scalar_one_or_none()
        if page is None:
            raise NotFoundError("Wiki page not found", details={"page_id": str(page_id)})
        return page

    def _get_claim(self, claim_id: uuid.UUID, *, for_update: bool = False) -> WikiClaim:
        stmt = select(WikiClaim).where(WikiClaim.id == claim_id, WikiClaim.owner_id == self.owner_id)
        if for_update:
            stmt = stmt.with_for_update()
        claim = self.db.execute(stmt).scalar_one_or_none()
        if claim is None:
            raise NotFoundError("Wiki claim not found", details={"claim_id": str(claim_id)})
        return claim

    def _ensure_page(
        self,
        *,
        slug: str,
        title: str,
        kind: str,
        source_document_id: uuid.UUID | None = None,
    ) -> WikiPage:
        page = self.db.execute(
            select(WikiPage).where(WikiPage.owner_id == self.owner_id, WikiPage.slug == slug).with_for_update()
        ).scalar_one_or_none()
        if page is None:
            page = WikiPage(
                owner_id=self.owner_id,
                slug=slug,
                title=title,
                kind=kind,
                status="needs_review",
                source_document_id=source_document_id,
                search_text="",
            )
            self.db.add(page)
            self.db.flush()
            self._event("page_created", page_id=page.id, payload={"kind": kind, "slug": slug})
        else:
            page.title = title
            if source_document_id is not None:
                page.source_document_id = source_document_id
        return page

    def _next_revision_number(self, page_id: uuid.UUID) -> int:
        current = self.db.scalar(
            select(func.max(WikiPageRevision.revision_number)).where(WikiPageRevision.page_id == page_id)
        )
        return int(current or 0) + 1

    def _create_revision(
        self,
        page: WikiPage,
        markdown: str,
        *,
        created_by: str,
        reason: str,
        model_name: str | None = None,
        prompt_version: str | None = WIKI_PROMPT_VERSION,
        force: bool = False,
    ) -> WikiPageRevision:
        normalized_markdown = str(markdown or "").strip()
        content_hash = sha256_text(normalized_markdown)
        if page.current_revision_id and not force:
            current = self.db.get(WikiPageRevision, page.current_revision_id)
            if current is not None and current.content_hash == content_hash:
                return current
        revision = WikiPageRevision(
            owner_id=self.owner_id,
            page_id=page.id,
            revision_number=self._next_revision_number(page.id),
            markdown=normalized_markdown,
            content_hash=content_hash,
            based_on_revision_id=page.current_revision_id,
            schema_version=WIKI_SCHEMA_VERSION,
            prompt_version=prompt_version,
            model_name=model_name,
            created_by=created_by,
            change_reason=reason,
        )
        self.db.add(revision)
        self.db.flush()
        page.current_revision_id = revision.id
        page.search_text = compact_text(normalized_markdown, 40_000)
        page.updated_at = datetime.now(timezone.utc)
        self._event("revision_created", page_id=page.id, revision_id=revision.id, payload={"reason": reason})
        return revision

    def _find_candidate_evidence(
        self,
        document: Document,
        chunks: list[DocumentChunk],
        variants: Iterable[str],
    ) -> list[WikiEvidenceCandidate]:
        normalized_variants = [compact_text(item) for item in variants if compact_text(item)]
        for chunk in chunks:
            for variant in normalized_variants:
                quote = _quote_window(chunk.text, variant)
                if quote:
                    return [
                        WikiEvidenceCandidate(
                            document_id=document.id,
                            chunk_id=chunk.id,
                            quote=quote,
                            support_role="supports",
                        )
                    ]
        return []

    def _document_candidates(self, document: Document, chunks: list[DocumentChunk]) -> list[WikiClaimCandidate]:
        title = _title(document)
        subject = title
        candidates: list[WikiClaimCandidate] = []

        document_type = compact_text(document.document_type or document.ai_document_type)
        if document_type:
            candidates.append(
                WikiClaimCandidate(
                    stable_key="document-type",
                    text=f"Dokumenttyp: {document_type}",
                    subject=subject,
                    predicate="document_type",
                    object_text=document_type,
                    claim_type="fact",
                    confidence=document.ai_confidence,
                    evidence=self._find_candidate_evidence(document, chunks, [document_type]),
                )
            )

        document_date = document.document_date or document.ai_document_date
        if document_date:
            candidates.append(
                WikiClaimCandidate(
                    stable_key="document-date",
                    text=f"Dokumentdatum: {document_date.strftime('%d.%m.%Y')}",
                    subject=subject,
                    predicate="document_date",
                    object_text=document_date.isoformat(),
                    claim_type="fact",
                    confidence=document.document_date_confidence or document.ai_confidence,
                    valid_from=document_date,
                    evidence=self._find_candidate_evidence(document, chunks, _date_variants(document_date)),
                )
            )

        sender = compact_text(document.ai_sender)
        if sender:
            candidates.append(
                WikiClaimCandidate(
                    stable_key="sender",
                    text=f"Absender: {sender}",
                    subject=subject,
                    predicate="sender",
                    object_text=sender,
                    claim_type="fact",
                    confidence=document.ai_confidence,
                    evidence=self._find_candidate_evidence(document, chunks, [sender]),
                )
            )

        recipient = compact_text(document.ai_recipient)
        if recipient:
            candidates.append(
                WikiClaimCandidate(
                    stable_key="recipient",
                    text=f"Empfänger: {recipient}",
                    subject=subject,
                    predicate="recipient",
                    object_text=recipient,
                    claim_type="fact",
                    confidence=document.ai_confidence,
                    evidence=self._find_candidate_evidence(document, chunks, [recipient]),
                )
            )

        if document.ai_amount is not None:
            amount = _format_amount(document.ai_amount, document.ai_currency)
            candidates.append(
                WikiClaimCandidate(
                    stable_key="amount",
                    text=f"Betrag: {amount}",
                    subject=subject,
                    predicate="amount",
                    object_text=amount,
                    claim_type="fact",
                    confidence=document.ai_confidence,
                    valid_from=document_date,
                    evidence=self._find_candidate_evidence(
                        document,
                        chunks,
                        _amount_variants(document.ai_amount, document.ai_currency),
                    ),
                )
            )
        return candidates

    @staticmethod
    def _render_source_page(
        document: Document,
        valid_results: list[ClaimValidationResult],
        unresolved_count: int,
    ) -> str:
        lines = [
            f"# {_title(document)}",
            "",
            "> Abgeleitete Wissensseite. Verbindlich ist ausschließlich das verknüpfte Originaldokument.",
            "",
            "## Quellenbelegte Aussagen",
        ]
        if valid_results:
            for result in valid_results:
                lines.append(f"- {result.candidate.text}")
        else:
            lines.append("- Noch keine automatisch überprüfbare Aussage vorhanden.")
        if unresolved_count:
            lines.extend(
                [
                    "",
                    "## Zu prüfen",
                    f"- {unresolved_count} Metadaten-Aussage(n) konnten nicht direkt im OCR-Text belegt werden.",
                ]
            )
        summary = compact_text(document.ai_summary, 900)
        if summary:
            lines.extend(
                [
                    "",
                    "## Ungeprüfte Arbeitsnotiz",
                    "> Diese Zusammenfassung ist kein Faktenbeleg und wird vom Chat nicht als Quelle verwendet.",
                    summary,
                ]
            )
        lines.extend(["", "## Original", f"- Dokument-ID: `{document.id}`"])
        return "\n".join(lines)

    def _evidence_model(self, row: WikiClaimEvidence) -> WikiEvidenceRead:
        document = self.db.get(Document, row.document_id)
        chunk = self.db.get(DocumentChunk, row.chunk_id)
        valid = bool(document and chunk and self.validator.evidence_row_is_current(row, document, chunk))
        return WikiEvidenceRead(
            id=row.id,
            document_id=row.document_id,
            chunk_id=row.chunk_id,
            page_from=row.page_from,
            page_to=row.page_to,
            quote=row.quote,
            support_role=row.support_role,
            chunk_content_hash=row.chunk_content_hash,
            document_text_hash=row.document_text_hash,
            valid=valid,
            document_title=_title(document) if document else None,
        )

    def _claim_model(self, claim: WikiClaim) -> WikiClaimRead:
        return WikiClaimRead(
            id=claim.id,
            page_id=claim.page_id,
            revision_id=claim.revision_id,
            stable_key=claim.stable_key,
            text=claim.text,
            subject=claim.subject,
            predicate=claim.predicate,
            object_text=claim.object_text,
            claim_type=claim.claim_type,
            status=claim.status,
            confidence=claim.confidence,
            valid_from=claim.valid_from,
            valid_to=claim.valid_to,
            supersedes_claim_id=claim.supersedes_claim_id,
            source_document_id=claim.source_document_id,
            locked_by_user=claim.locked_by_user,
            created_by=claim.created_by,
            created_at=claim.created_at,
            updated_at=claim.updated_at,
            evidence=[self._evidence_model(row) for row in claim.evidence],
        )

    def _add_validated_claim(
        self,
        page: WikiPage,
        revision: WikiPageRevision,
        result: ClaimValidationResult,
        *,
        source_document_id: uuid.UUID | None,
        created_by: str,
        locked_by_user: bool = False,
        supersedes_claim_id: uuid.UUID | None = None,
        forced_status: str | None = None,
    ) -> WikiClaim:
        candidate = result.candidate
        status = forced_status or ("active" if result.valid_for_activation else "needs_review")
        claim = WikiClaim(
            owner_id=self.owner_id,
            page_id=page.id,
            revision_id=revision.id,
            stable_key=candidate.stable_key,
            text=candidate.text,
            subject=candidate.subject,
            predicate=candidate.predicate,
            object_text=candidate.object_text,
            claim_type=candidate.claim_type.value,
            status=status,
            confidence=candidate.confidence,
            valid_from=candidate.valid_from,
            valid_to=candidate.valid_to,
            supersedes_claim_id=supersedes_claim_id,
            source_document_id=source_document_id,
            locked_by_user=locked_by_user,
            created_by=created_by,
        )
        self.db.add(claim)
        self.db.flush()
        for item in result.evidence:
            self.db.add(
                WikiClaimEvidence(
                    owner_id=self.owner_id,
                    claim_id=claim.id,
                    document_id=item.document.id,
                    chunk_id=item.chunk.id,
                    page_from=item.chunk.page_from,
                    page_to=item.chunk.page_to,
                    quote=item.quote,
                    quote_hash=item.quote_hash,
                    chunk_content_hash=item.chunk.content_hash,
                    document_text_hash=item.document.text_hash,
                    support_role=item.support_role,
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                )
            )
        self._event("claim_created", page_id=page.id, revision_id=revision.id, claim_id=claim.id, payload={"status": status})
        return claim

    def _proposal(
        self,
        *,
        proposal_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        status: str,
        page: WikiPage | None = None,
        document: Document | None = None,
        revision: WikiPageRevision | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        model_name: str | None = None,
    ) -> WikiUpdateProposal:
        existing = self.db.execute(
            select(WikiUpdateProposal).where(
                WikiUpdateProposal.owner_id == self.owner_id,
                WikiUpdateProposal.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if status == "pending" and revision is not None and existing.status == "pending":
                existing.base_revision_id = revision.id
            return existing
        now = datetime.now(timezone.utc)
        if status == "pending" and document is not None:
            older_pending = list(
                self.db.execute(
                    select(WikiUpdateProposal).where(
                        WikiUpdateProposal.owner_id == self.owner_id,
                        WikiUpdateProposal.source_document_id == document.id,
                        WikiUpdateProposal.proposal_type == proposal_type,
                        WikiUpdateProposal.status == "pending",
                    )
                ).scalars()
            )
            for older in older_pending:
                older.status = "rejected"
                older.reviewed_at = now
                older.review_note = "Automatisch durch eine neuere Dokumentrevision ersetzt"
                self._event(
                    "proposal_superseded",
                    page_id=older.page_id,
                    proposal_id=older.id,
                    payload={"replacement_key": idempotency_key},
                )
        proposal = WikiUpdateProposal(
            owner_id=self.owner_id,
            source_document_id=document.id if document else None,
            page_id=page.id if page else None,
            base_revision_id=(
                revision.id
                if revision is not None and status in {"pending", "validated"}
                else revision.based_on_revision_id
                if revision is not None
                else page.current_revision_id
                if page is not None
                else None
            ),
            applied_revision_id=revision.id if revision and status == "applied" else None,
            proposal_type=proposal_type,
            status=status,
            payload=payload,
            validation_errors=validation_errors,
            idempotency_key=idempotency_key,
            schema_version=WIKI_SCHEMA_VERSION,
            prompt_version=WIKI_PROMPT_VERSION,
            model_name=model_name,
            applied_at=now if status == "applied" else None,
        )
        self.db.add(proposal)
        self.db.flush()
        self._event(
            "proposal_created",
            page_id=proposal.page_id,
            revision_id=proposal.applied_revision_id,
            proposal_id=proposal.id,
            payload={"status": status, "type": proposal_type},
        )
        return proposal

    def _upsert_link(self, from_page: WikiPage, to_page: WikiPage, relation: str) -> WikiLink:
        link = self.db.execute(
            select(WikiLink).where(
                WikiLink.owner_id == self.owner_id,
                WikiLink.from_page_id == from_page.id,
                WikiLink.to_page_id == to_page.id,
                WikiLink.relation == relation,
            )
        ).scalar_one_or_none()
        if link is None:
            link = WikiLink(
                owner_id=self.owner_id,
                from_page_id=from_page.id,
                to_page_id=to_page.id,
                relation=relation,
                status="active",
            )
            self.db.add(link)
        else:
            link.status = "active"
        return link

    def _refresh_aggregate_page(self, page: WikiPage, *, reason: str) -> WikiPageRevision:
        source_page_ids = select(WikiLink.from_page_id).where(
            WikiLink.owner_id == self.owner_id,
            WikiLink.to_page_id == page.id,
            WikiLink.status == "active",
        )
        source_count = int(
            self.db.scalar(
                select(func.count(func.distinct(WikiLink.from_page_id))).where(
                    WikiLink.owner_id == self.owner_id,
                    WikiLink.to_page_id == page.id,
                    WikiLink.status == "active",
                )
            )
            or 0
        )
        active_count = int(
            self.db.scalar(
                select(func.count()).select_from(WikiClaim).where(
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.page_id.in_(source_page_ids),
                    WikiClaim.status == "active",
                )
            )
            or 0
        )
        rows = list(
            self.db.execute(
                select(WikiPage, WikiClaim)
                .join(WikiClaim, WikiClaim.page_id == WikiPage.id)
                .where(
                    WikiPage.id.in_(source_page_ids),
                    WikiPage.owner_id == self.owner_id,
                    WikiClaim.status == "active",
                )
                .order_by(
                    WikiClaim.valid_from.desc().nullslast(),
                    WikiClaim.created_at.desc(),
                    WikiClaim.id.desc(),
                )
                .limit(AGGREGATE_RECENT_CLAIM_LIMIT)
            ).all()
        )
        lines = [
            f"# {page.title}",
            "",
            "> Automatisch aus verlinkten, quellengestützten Seiten zusammengestellt.",
            "",
            "## Überblick",
            f"- {active_count} belegte Aussagen aus {source_count} Quellen",
            "",
            f"## Neueste belegte Aussagen (maximal {AGGREGATE_RECENT_CLAIM_LIMIT})",
        ]
        if not rows:
            lines.append("- Noch keine aktiven, quellengestützten Aussagen vorhanden.")
        for source_page, claim in rows:
            lines.append(f"- **{source_page.title}:** {claim.text}")
        revision = self._create_revision(page, "\n".join(lines), created_by="system", reason=reason)
        page.status = "active" if active_count else "needs_review"
        return revision

    def compact_large_aggregate_pages(self, *, commit: bool = True) -> int:
        """Rewrite only aggregates whose live claim set exceeds the render cap.

        This is primarily a one-time compatibility pass for installations that
        already had unbounded aggregate revisions before the cap was added. The
        candidate lookup is set-based, so a 500-document library does not turn
        into a scan-and-rewrite loop over every wiki page.
        """

        candidate_ids = (
            select(WikiLink.to_page_id)
            .join(
                WikiClaim,
                and_(
                    WikiClaim.page_id == WikiLink.from_page_id,
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.status == "active",
                ),
            )
            .where(
                WikiLink.owner_id == self.owner_id,
                WikiLink.status == "active",
            )
            .group_by(WikiLink.to_page_id)
            .having(func.count(WikiClaim.id) > AGGREGATE_RECENT_CLAIM_LIMIT)
        )
        pages = list(
            self.db.execute(
                select(WikiPage).where(
                    WikiPage.owner_id == self.owner_id,
                    WikiPage.kind.in_(("entity", "contract", "topic", "timeline", "comparison")),
                    WikiPage.id.in_(candidate_ids),
                )
            ).scalars()
        )
        changed_page_ids: list[uuid.UUID] = []
        for page in pages:
            previous_revision_id = page.current_revision_id
            revision = self._refresh_aggregate_page(page, reason="Aggregat auf aktuelle Größenbegrenzung gebracht")
            if revision.id != previous_revision_id:
                changed_page_ids.append(page.id)

        if changed_page_ids:
            from app.services.wiki_search import WikiSearchService

            WikiSearchService(self.db, self.owner_id).refresh_page_embeddings(changed_page_ids)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return len(changed_page_ids)

    def _refresh_navigation_pages(self, document: Document, source_page: WikiPage) -> list[uuid.UUID]:
        touched: list[uuid.UUID] = []
        # Canonical correspondent IDs are deterministic entity anchors. Raw LLM
        # sender strings are intentionally not merged into entity pages.
        if document.correspondent_id:
            correspondent = self.db.execute(
                select(Correspondent).where(
                    Correspondent.id == document.correspondent_id,
                    Correspondent.owner_id == self.owner_id,
                )
            ).scalar_one_or_none()
            if correspondent:
                entity = self._ensure_page(
                    slug=f"korrespondent-{correspondent.id}",
                    title=correspondent.name,
                    kind="entity",
                )
                self._upsert_link(source_page, entity, "about_entity")
                self._refresh_aggregate_page(entity, reason=f"Quelle {_title(document)} aktualisiert")
                touched.append(entity.id)

        document_type = compact_text(document.document_type or document.ai_document_type)
        if document_type:
            topic = self._ensure_page(
                slug=f"dokumenttyp-{_slugify(document_type)}",
                title=document_type,
                kind="topic",
            )
            self._upsert_link(source_page, topic, "about_topic")
            self._refresh_aggregate_page(topic, reason=f"Quelle {_title(document)} aktualisiert")
            touched.append(topic.id)

            if any(marker in document_type.casefold() for marker in _CONTRACT_MARKERS):
                contract = self._ensure_page(
                    slug=f"vertrag-{document.id}",
                    title=f"Vertrag · {_title(document)}",
                    kind="contract",
                )
                self._upsert_link(source_page, contract, "describes_contract")
                self._refresh_aggregate_page(contract, reason="Vertragsquelle aktualisiert")
                touched.append(contract.id)

        timeline = self._ensure_page(slug="zeitachse", title="Zeitachse", kind="timeline")
        self._upsert_link(source_page, timeline, "appears_in_timeline")
        self._refresh_aggregate_page(timeline, reason=f"Quelle {_title(document)} aktualisiert")
        touched.append(timeline.id)
        return touched

    def refresh_document(
        self,
        document: Document | uuid.UUID,
        *,
        commit: bool = True,
        include_navigation: bool = True,
    ) -> dict[str, Any]:
        document_id = document.id if isinstance(document, Document) else document
        loaded = self.db.execute(
            select(Document)
            .where(Document.id == document_id, Document.owner_id == self.owner_id)
            .options(selectinload(Document.chunks))
        ).scalar_one_or_none()
        if loaded is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        if loaded.is_deleted:
            self.mark_document_unavailable(loaded.id, reason="document_trashed", commit=commit)
            return {"updated": False, "review_proposals": 0, "page_id": None}

        chunks = list(loaded.chunks)
        chunk_signature = sha256_text("|".join(f"{chunk.id}:{chunk.content_hash}" for chunk in chunks))
        idempotency_base = sha256_text(
            f"source:{loaded.id}:{loaded.text_hash or ''}:{chunk_signature}:{WIKI_SCHEMA_VERSION}"
        )
        existing = self.db.execute(
            select(WikiUpdateProposal).where(
                WikiUpdateProposal.owner_id == self.owner_id,
                WikiUpdateProposal.idempotency_key == idempotency_base,
                WikiUpdateProposal.status == "applied",
            )
        ).scalar_one_or_none()
        if existing is not None:
            page_status = self.db.scalar(
                select(WikiPage.status).where(
                    WikiPage.id == existing.page_id,
                    WikiPage.owner_id == self.owner_id,
                )
            ) if existing.page_id else None
            # A trashed source page is explicitly marked stale and must be
            # reactivated after restore. Historical stale claims from older
            # revisions, however, must never turn every backfill into another
            # expensive LLM compilation.
            if page_status != "stale":
                return {
                    "updated": False,
                    "review_proposals": 0,
                    "page_id": str(existing.page_id) if existing.page_id else None,
                }
            current_revision_id = self.db.scalar(
                select(WikiPage.current_revision_id).where(WikiPage.id == existing.page_id)
            )
            idempotency_base = sha256_text(f"{idempotency_base}:reactivate:{current_revision_id or ''}")

        candidates = self._document_candidates(loaded, chunks)
        extraction_model: str | None = None
        prompt_version = WIKI_PROMPT_VERSION
        runtime_settings = SettingsService(self.db).get_settings()
        if (
            runtime_settings.wiki.llm_claim_extraction
            and runtime_settings.ollama.enabled
            and chunks
        ):
            extraction = WikiClaimExtractionService(
                base_url=runtime_settings.ollama.base_url,
                model=runtime_settings.ollama.model,
                timeout_seconds=runtime_settings.ollama.timeout_seconds,
            ).extract(loaded, chunks)
            extraction_model = extraction.model_name
            prompt_version = extraction.prompt_version
            existing_keys = {candidate.stable_key for candidate in candidates}
            candidates.extend(candidate for candidate in extraction.claims if candidate.stable_key not in existing_keys)
        results = [self.validator.validate_claim(candidate) for candidate in candidates]
        valid_results = [result for result in results if result.valid_for_activation]
        invalid_results = [result for result in results if not result.valid_for_activation]

        page = self._ensure_page(
            slug=f"quelle-{loaded.id}",
            title=_title(loaded),
            kind="source",
            source_document_id=loaded.id,
        )
        old_claims = list(
            self.db.execute(
                select(WikiClaim).where(
                    WikiClaim.page_id == page.id,
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.status.in_(("active", "needs_review", "disputed", "stale")),
                )
            ).scalars()
        )
        old_by_key: dict[str, list[WikiClaim]] = {}
        for old_claim in old_claims:
            old_by_key.setdefault(old_claim.stable_key, []).append(old_claim)

        markdown = self._render_source_page(loaded, valid_results, len(invalid_results))
        revision = self._create_revision(
            page,
            markdown,
            created_by="system",
            reason="Dokument neu belegt oder aktualisiert",
            model_name=extraction_model,
            prompt_version=prompt_version,
            force=True,
        )

        new_claims: list[WikiClaim] = []
        valid_keys: set[str] = set()
        for result in valid_results:
            valid_keys.add(result.candidate.stable_key)
            previous = next(
                (
                    item
                    for item in reversed(old_by_key.get(result.candidate.stable_key, []))
                    if item.status in _ACTIVE_CLAIM_STATUSES or item.status == "stale"
                ),
                None,
            )
            forced_status = None
            if previous and previous.locked_by_user and previous.object_text != result.candidate.object_text:
                forced_status = "disputed"
            claim = self._add_validated_claim(
                page,
                revision,
                result,
                source_document_id=loaded.id,
                created_by="system",
                supersedes_claim_id=previous.id if previous and not previous.locked_by_user else None,
                forced_status=forced_status,
            )
            new_claims.append(claim)
            if previous and not previous.locked_by_user:
                previous.status = "superseded"
                previous.updated_at = datetime.now(timezone.utc)

        for old_claim in old_claims:
            if old_claim.stable_key not in valid_keys and not old_claim.locked_by_user and old_claim.status == "active":
                old_claim.status = "stale"
                old_claim.updated_at = datetime.now(timezone.utc)

        page.status = "active" if (
            any(claim.status == "active" for claim in new_claims)
            or any(claim.locked_by_user and claim.status == "active" for claim in old_claims)
        ) else "needs_review"
        applied_payload = {
            "document_id": str(loaded.id),
            "claims": [result.candidate.model_dump(mode="json") for result in valid_results],
            "source_text_hash": loaded.text_hash,
        }
        applied_proposal = self._proposal(
            proposal_type="document_compile",
            idempotency_key=idempotency_base,
            payload=applied_payload,
            status="applied",
            page=page,
            document=loaded,
            revision=revision,
            model_name=extraction_model,
        )

        review_count = 0
        if invalid_results:
            errors = [
                {
                    "stable_key": result.candidate.stable_key,
                    "errors": list(result.errors),
                }
                for result in invalid_results
            ]
            self._proposal(
                proposal_type="unverified_document_claims",
                idempotency_key=f"{idempotency_base}-review",
                payload={
                    "document_id": str(loaded.id),
                    "page_id": str(page.id),
                    "claims": [result.candidate.model_dump(mode="json") for result in invalid_results],
                },
                status="pending",
                page=page,
                document=loaded,
                revision=revision,
                validation_errors=errors,
                model_name=extraction_model,
            )
            review_count = 1

        navigation_page_ids: list[uuid.UUID] = []
        if include_navigation:
            navigation_page_ids = self._refresh_navigation_pages(loaded, page)

        # One small batched embedding request makes page retrieval hybrid. It is
        # best-effort and never weakens the source-grounding transaction.
        from app.services.wiki_search import WikiSearchService

        WikiSearchService(self.db, self.owner_id).refresh_page_embeddings([page.id, *navigation_page_ids])

        self._event(
            "document_compiled",
            page_id=page.id,
            revision_id=revision.id,
            proposal_id=applied_proposal.id,
            payload={"active_claims": len(valid_results), "review_claims": len(invalid_results)},
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return {
            "updated": True,
            "review_proposals": review_count,
            "page_id": str(page.id),
            "active_claims": len(valid_results),
        }

    def mark_document_unavailable(self, document_id: uuid.UUID, *, reason: str, commit: bool = True) -> int:
        claims = list(
            self.db.execute(
                select(WikiClaim).where(
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.source_document_id == document_id,
                    WikiClaim.status.in_(("active", "disputed", "needs_review")),
                )
            ).scalars()
        )
        page_ids: set[uuid.UUID] = set()
        permanent = reason in {"document_deleted", "document_purged"}
        for claim in claims:
            claim.status = "retracted" if permanent else "stale"
            claim.updated_at = datetime.now(timezone.utc)
            page_ids.add(claim.page_id)
        pages = list(
            self.db.execute(
                select(WikiPage).where(
                    WikiPage.owner_id == self.owner_id,
                    or_(WikiPage.source_document_id == document_id, WikiPage.id.in_(page_ids) if page_ids else literal(False)),
                )
            ).scalars()
        )
        for page in pages:
            page.status = "archived" if permanent else "stale"
            page.updated_at = datetime.now(timezone.utc)
            self._event("page_stale", page_id=page.id, payload={"reason": reason, "document_id": str(document_id)})
        source_page_ids = [page.id for page in pages if page.source_document_id == document_id or page.kind == "source"]
        if source_page_ids:
            links = list(
                self.db.execute(
                    select(WikiLink).where(
                        WikiLink.owner_id == self.owner_id,
                        WikiLink.from_page_id.in_(source_page_ids),
                        WikiLink.status == "active",
                    )
                ).scalars()
            )
            target_ids = list(dict.fromkeys(link.to_page_id for link in links))
            for link in links:
                link.status = "retracted"
            for target_id in target_ids:
                target = self.db.get(WikiPage, target_id)
                if target is not None:
                    self._refresh_aggregate_page(target, reason=f"Quelle entfernt: {document_id}")
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return len(claims)

    def _page_counts(self, page_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        if not page_ids:
            return {}
        rows = self.db.execute(
            select(
                WikiClaim.page_id,
                func.count(WikiClaim.id).filter(WikiClaim.status == "active"),
                func.count(WikiClaim.id).filter(WikiClaim.status.in_(("needs_review", "stale"))),
                func.count(WikiClaim.id).filter(WikiClaim.status == "disputed"),
                func.count(func.distinct(WikiClaimEvidence.document_id)),
            )
            .outerjoin(WikiClaimEvidence, WikiClaimEvidence.claim_id == WikiClaim.id)
            .where(WikiClaim.page_id.in_(page_ids), WikiClaim.owner_id == self.owner_id)
            .group_by(WikiClaim.page_id)
        ).all()
        counts = {
            row[0]: {
                "active": int(row[1] or 0),
                "review": int(row[2] or 0),
                "conflict": int(row[3] or 0),
                "sources": int(row[4] or 0),
            }
            for row in rows
        }
        # Aggregate pages own no claims; sources are reached through active links.
        aggregate_rows = self.db.execute(
            select(WikiLink.to_page_id, func.count(func.distinct(WikiLink.from_page_id)))
            .where(
                WikiLink.owner_id == self.owner_id,
                WikiLink.to_page_id.in_(page_ids),
                WikiLink.status == "active",
            )
            .group_by(WikiLink.to_page_id)
        ).all()
        for page_id, source_count in aggregate_rows:
            counts.setdefault(page_id, {"active": 0, "review": 0, "conflict": 0, "sources": 0})["sources"] = int(source_count)
        return counts

    def list_pages(
        self,
        *,
        q: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> WikiPageListResponse:
        stmt = select(WikiPage).where(WikiPage.owner_id == self.owner_id)
        count_stmt = select(func.count()).select_from(WikiPage).where(WikiPage.owner_id == self.owner_id)
        if kind:
            stmt = stmt.where(WikiPage.kind == kind)
            count_stmt = count_stmt.where(WikiPage.kind == kind)
        if status:
            stmt = stmt.where(WikiPage.status == status)
            count_stmt = count_stmt.where(WikiPage.status == status)
        normalized_q = compact_text(q)
        if normalized_q:
            pattern = f"%{normalized_q}%"
            stmt = stmt.where(or_(WikiPage.title.ilike(pattern), WikiPage.search_text.ilike(pattern)))
            count_stmt = count_stmt.where(or_(WikiPage.title.ilike(pattern), WikiPage.search_text.ilike(pattern)))
        total = int(self.db.scalar(count_stmt) or 0)
        pages = list(
            self.db.execute(
                stmt.order_by(WikiPage.updated_at.desc(), WikiPage.title.asc(), WikiPage.id.asc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            ).scalars()
        )
        counts = self._page_counts([page.id for page in pages])
        return WikiPageListResponse(
            items=[self._page_list_item(page, counts.get(page.id)) for page in pages],
            total=total,
        )

    def _page_list_item(
        self,
        page: WikiPage,
        counts: dict[str, int] | None = None,
        *,
        score: float | None = None,
    ) -> WikiPageListItem:
        counts = counts or {"active": 0, "review": 0, "conflict": 0, "sources": 0}
        snippet = compact_text(page.search_text, 220) or None
        return WikiPageListItem(
            id=page.id,
            slug=page.slug,
            title=page.title,
            kind=page.kind,
            status=page.status,
            source_document_id=page.source_document_id,
            current_revision_id=page.current_revision_id,
            active_claim_count=counts.get("active", 0),
            review_claim_count=counts.get("review", 0),
            conflict_claim_count=counts.get("conflict", 0),
            source_count=counts.get("sources", 0),
            updated_at=page.updated_at,
            score=score,
            snippet=snippet,
        )

    def _claim_page_ids(self, page: WikiPage) -> list[uuid.UUID]:
        page_ids = [page.id]
        if page.kind != "source":
            page_ids.extend(
                self.db.scalars(
                    select(WikiLink.from_page_id).where(
                        WikiLink.owner_id == self.owner_id,
                        WikiLink.to_page_id == page.id,
                        WikiLink.status == "active",
                    )
                )
            )
        return list(dict.fromkeys(page_ids))

    def _claims_for_page(
        self,
        page: WikiPage,
        *,
        include_history: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[WikiClaim]:
        page_ids = self._claim_page_ids(page)
        stmt = (
            select(WikiClaim)
            .where(WikiClaim.owner_id == self.owner_id, WikiClaim.page_id.in_(page_ids))
            .options(selectinload(WikiClaim.evidence))
        )
        if not include_history:
            stmt = stmt.where(WikiClaim.status.in_(("active", "needs_review", "disputed", "stale")))
        stmt = (
            stmt.order_by(WikiClaim.created_at.desc(), WikiClaim.id.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
        )
        return list(self.db.execute(stmt).scalars().unique())

    def get_page_detail(
        self,
        page_id: uuid.UUID,
        *,
        include_history: bool = False,
        claim_limit: int = 200,
        claim_offset: int = 0,
    ) -> WikiPageDetail:
        page = self._get_page(page_id)
        current = self.db.get(WikiPageRevision, page.current_revision_id) if page.current_revision_id else None
        claim_page_ids = self._claim_page_ids(page)
        claim_filters = [WikiClaim.owner_id == self.owner_id, WikiClaim.page_id.in_(claim_page_ids)]
        if not include_history:
            claim_filters.append(WikiClaim.status.in_(("active", "needs_review", "disputed", "stale")))
        claim_total = int(
            self.db.scalar(select(func.count()).select_from(WikiClaim).where(*claim_filters)) or 0
        )
        claims = self._claims_for_page(
            page,
            include_history=include_history,
            limit=claim_limit,
            offset=claim_offset,
        )
        link_rows = self.db.execute(
            select(WikiLink, WikiPage)
            .join(
                WikiPage,
                or_(
                    and_(WikiLink.from_page_id == page.id, WikiPage.id == WikiLink.to_page_id),
                    and_(WikiLink.to_page_id == page.id, WikiPage.id == WikiLink.from_page_id),
                ),
            )
            .where(WikiLink.owner_id == self.owner_id, or_(WikiLink.from_page_id == page.id, WikiLink.to_page_id == page.id))
            .order_by(WikiPage.title.asc())
        ).all()
        counts = self._page_counts([page.id]).get(page.id)
        base = self._page_list_item(page, counts).model_dump()
        return WikiPageDetail(
            **base,
            markdown=current.markdown if current else "",
            current_revision=WikiRevisionRead.model_validate(current, from_attributes=True) if current else None,
            claims=[self._claim_model(claim) for claim in claims],
            claim_total=claim_total,
            links=[
                WikiLinkRead(
                    id=link.id,
                    from_page_id=link.from_page_id,
                    to_page_id=link.to_page_id,
                    relation=link.relation,
                    status=link.status,
                    linked_page_id=linked.id,
                    linked_page_title=linked.title,
                    linked_page_kind=linked.kind,
                )
                for link, linked in link_rows
            ],
            revision_count=int(
                self.db.scalar(select(func.count()).select_from(WikiPageRevision).where(WikiPageRevision.page_id == page.id)) or 0
            ),
        )

    def list_revisions(self, page_id: uuid.UUID) -> list[WikiRevisionRead]:
        self._get_page(page_id)
        rows = self.db.execute(
            select(WikiPageRevision)
            .where(WikiPageRevision.page_id == page_id, WikiPageRevision.owner_id == self.owner_id)
            .order_by(WikiPageRevision.revision_number.desc())
        ).scalars()
        return [WikiRevisionRead.model_validate(row, from_attributes=True) for row in rows]

    def _render_active_claims(self, page: WikiPage, *, replacement: WikiClaimCandidate | None = None, remove_id: uuid.UUID | None = None) -> str:
        claims = list(
            self.db.execute(
                select(WikiClaim).where(
                    WikiClaim.owner_id == self.owner_id,
                    WikiClaim.page_id == page.id,
                    WikiClaim.status.in_(("active", "disputed")),
                    WikiClaim.id != remove_id if remove_id else literal(True),
                )
                .order_by(WikiClaim.stable_key.asc(), WikiClaim.created_at.asc())
            ).scalars()
        )
        lines = [f"# {page.title}", "", "> Versionierte Wissensseite mit nachverfolgbaren Aussagen.", "", "## Aussagen"]
        lines.extend(f"- {claim.text}" for claim in claims)
        if replacement:
            lines.append(f"- {replacement.text}")
        if len(lines) == 5:
            lines.append("- Keine aktiven Aussagen.")
        return "\n".join(lines)

    def correct_claim(
        self,
        claim_id: uuid.UUID,
        payload: WikiClaimCorrectionRequest,
        *,
        commit: bool = True,
    ) -> WikiPageDetail:
        claim = self._get_claim(claim_id, for_update=True)
        page = self._get_page(claim.page_id, for_update=True)
        if page.current_revision_id != payload.expected_revision_id:
            raise ConflictError(
                "Wiki page changed since it was opened",
                details={"current_revision_id": str(page.current_revision_id)},
            )
        candidate = WikiClaimCandidate(
            stable_key=claim.stable_key,
            text=payload.corrected_text,
            subject=payload.subject,
            predicate=payload.predicate or claim.predicate,
            object_text=payload.object_text,
            claim_type=payload.claim_type,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            evidence=payload.evidence,
        )
        if candidate.claim_type == WikiClaimType.fact and not any(
            normalized_evidence_text(candidate.text) in normalized_evidence_text(item.quote)
            for item in candidate.evidence
            if item.support_role.value == "supports"
        ):
            raise BadRequestError(
                "Corrected factual text must occur verbatim in a supporting quote",
                details={"field": "corrected_text"},
            )
        result = self.validator.validate_claim(candidate)
        if not result.valid_for_activation:
            raise BadRequestError("Corrected claim is not source-grounded", details={"errors": list(result.errors)})

        markdown = self._render_active_claims(page, replacement=candidate, remove_id=claim.id)
        revision = self._create_revision(
            page,
            markdown,
            created_by="user",
            reason=payload.reason,
            prompt_version=None,
        )
        new_claim = self._add_validated_claim(
            page,
            revision,
            result,
            source_document_id=(result.evidence[0].document.id if result.evidence else claim.source_document_id),
            created_by="user",
            locked_by_user=payload.lock_after_correction,
            supersedes_claim_id=claim.id,
        )
        claim.status = "superseded"
        claim.updated_at = datetime.now(timezone.utc)
        page.status = "active"
        self._event(
            "claim_corrected",
            page_id=page.id,
            revision_id=revision.id,
            claim_id=new_claim.id,
            payload={"superseded_claim_id": str(claim.id)},
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_page_detail(page.id)

    def retract_claim(
        self,
        claim_id: uuid.UUID,
        payload: WikiClaimRetractRequest,
        *,
        commit: bool = True,
    ) -> WikiPageDetail:
        claim = self._get_claim(claim_id, for_update=True)
        page = self._get_page(claim.page_id, for_update=True)
        if page.current_revision_id != payload.expected_revision_id:
            raise ConflictError(
                "Wiki page changed since it was opened",
                details={"current_revision_id": str(page.current_revision_id)},
            )
        claim.status = "retracted"
        claim.updated_at = datetime.now(timezone.utc)
        markdown = self._render_active_claims(page, remove_id=claim.id)
        revision = self._create_revision(page, markdown, created_by="user", reason=payload.reason, prompt_version=None)
        remaining = int(
            self.db.scalar(
                select(func.count()).select_from(WikiClaim).where(
                    WikiClaim.page_id == page.id,
                    WikiClaim.status == "active",
                    WikiClaim.id != claim.id,
                )
            )
            or 0
        )
        page.status = "active" if remaining else "needs_review"
        self._event("claim_retracted", page_id=page.id, revision_id=revision.id, claim_id=claim.id, payload={"reason": payload.reason})
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_page_detail(page.id)

    def list_proposals(
        self,
        *,
        status: str | None = "pending",
        limit: int = 100,
        offset: int = 0,
    ) -> WikiProposalListResponse:
        stmt = select(WikiUpdateProposal).where(WikiUpdateProposal.owner_id == self.owner_id)
        count_stmt = select(func.count()).select_from(WikiUpdateProposal).where(WikiUpdateProposal.owner_id == self.owner_id)
        if status:
            stmt = stmt.where(WikiUpdateProposal.status == status)
            count_stmt = count_stmt.where(WikiUpdateProposal.status == status)
        rows = list(
            self.db.execute(
                stmt.order_by(WikiUpdateProposal.created_at.desc(), WikiUpdateProposal.id.desc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            ).scalars()
        )
        return WikiProposalListResponse(
            items=[WikiProposalRead.model_validate(row, from_attributes=True) for row in rows],
            total=int(self.db.scalar(count_stmt) or 0),
        )

    def review_proposal(
        self,
        proposal_id: uuid.UUID,
        payload: WikiProposalReviewRequest,
        *,
        reviewer_id: uuid.UUID,
    ) -> WikiProposalRead:
        proposal = self.db.execute(
            select(WikiUpdateProposal)
            .where(WikiUpdateProposal.id == proposal_id, WikiUpdateProposal.owner_id == self.owner_id)
            .with_for_update()
        ).scalar_one_or_none()
        if proposal is None:
            raise NotFoundError("Wiki proposal not found", details={"proposal_id": str(proposal_id)})
        if proposal.status not in {"pending", "validated"}:
            raise ConflictError("Wiki proposal has already been reviewed")
        now = datetime.now(timezone.utc)
        if payload.action == "reject":
            proposal.status = "rejected"
            proposal.reviewed_by = reviewer_id
            proposal.review_note = compact_text(payload.note, 2000) or None
            proposal.reviewed_at = now
            self._event("proposal_rejected", proposal_id=proposal.id, page_id=proposal.page_id)
            self.db.commit()
            return WikiProposalRead.model_validate(proposal, from_attributes=True)

        if proposal.proposal_type == "chat_analysis":
            title = compact_text(proposal.payload.get("title"), 240) or "Gespeicherte Analyse"
            page = self._ensure_page(
                slug=f"analyse-{_slugify(title)}-{str(proposal.id)[:8]}",
                title=title,
                kind="analysis",
            )
            revision = self._create_revision(
                page,
                str(proposal.payload.get("content") or ""),
                created_by="user",
                reason=payload.note or "Wissensanalyse übernommen",
                prompt_version=None,
            )
            # A manually retained chat answer is useful working material, but
            # it is not an active fact merely because a human kept the prose.
            # Only atomic claims that pass source validation become active.
            page.status = "needs_review"
            proposal.page_id = page.id
            proposal.applied_revision_id = revision.id
        else:
            if proposal.page_id is None:
                raise BadRequestError("Proposal has no target page")
            page = self._get_page(proposal.page_id, for_update=True)
            if proposal.base_revision_id != page.current_revision_id:
                raise ConflictError(
                    "Wiki proposal targets an older page revision",
                    details={"current_revision_id": str(page.current_revision_id)},
                )
            raw_claims = payload.accepted_claims
            if raw_claims is None:
                raw_claims = [WikiClaimCandidate.model_validate(item) for item in proposal.payload.get("claims") or []]
            if not raw_claims:
                raise BadRequestError("Proposal contains no claims to accept")
            results = [self.validator.validate_claim(item) for item in raw_claims]
            invalid = [item for item in results if not item.valid_for_activation]
            if invalid:
                raise BadRequestError(
                    "Accepted proposal still contains unsupported facts",
                    details={"errors": [list(item.errors) for item in invalid]},
                )
            markdown = self._render_active_claims(page)
            markdown += "\n" + "\n".join(f"- {item.candidate.text}" for item in results)
            revision = self._create_revision(
                page,
                markdown,
                created_by="user",
                reason=payload.note or "Wissensvorschlag bestätigt",
                prompt_version=None,
            )
            for result in results:
                self._add_validated_claim(
                    page,
                    revision,
                    result,
                    source_document_id=result.evidence[0].document.id if result.evidence else proposal.source_document_id,
                    created_by="user",
                    locked_by_user=True,
                )
            page.status = "active"
            proposal.applied_revision_id = revision.id

        proposal.status = "applied"
        proposal.reviewed_by = reviewer_id
        proposal.review_note = compact_text(payload.note, 2000) or None
        proposal.reviewed_at = now
        proposal.applied_at = now
        self._event(
            "proposal_applied",
            proposal_id=proposal.id,
            page_id=proposal.page_id,
            revision_id=proposal.applied_revision_id,
        )
        self.db.commit()
        return WikiProposalRead.model_validate(proposal, from_attributes=True)

    def capture_chat_answer(self, payload: WikiCaptureAnswerRequest) -> WikiProposalRead:
        message = ChatSessionService(self.db, self.owner_id).get_assistant_message(payload.session_id, payload.message_id)
        key = sha256_text(f"chat:{message.id}:{message.content}:{payload.title}")
        existing = self.db.execute(
            select(WikiUpdateProposal).where(
                WikiUpdateProposal.owner_id == self.owner_id,
                WikiUpdateProposal.idempotency_key == key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return WikiProposalRead.model_validate(existing, from_attributes=True)
        session_id = message.session_id
        proposal = WikiUpdateProposal(
            owner_id=self.owner_id,
            source_chat_session_id=session_id,
            proposal_type="chat_analysis",
            status="pending",
            payload={
                "title": payload.title,
                "content": message.content,
                "citations": message.citations,
                "knowledge_trace": message.knowledge_trace,
            },
            validation_errors=None,
            idempotency_key=key,
            schema_version=WIKI_SCHEMA_VERSION,
            prompt_version=None,
            model_name=None,
        )
        self.db.add(proposal)
        self.db.flush()
        self._event("chat_capture_proposed", proposal_id=proposal.id, payload={"message_id": str(message.id)})
        self.db.commit()
        return WikiProposalRead.model_validate(proposal, from_attributes=True)

    def lint(self, *, fix: bool = True) -> WikiLintResponse:
        issues: list[WikiLintIssue] = []
        fixed = 0
        claims = list(
            self.db.execute(
                select(WikiClaim).where(WikiClaim.owner_id == self.owner_id)
            ).scalars()
        )
        # One set-based provenance read replaces two point queries per evidence
        # row. This keeps the daily sweep predictable with thousands of claims.
        evidence_by_claim: dict[
            uuid.UUID,
            list[tuple[WikiClaimEvidence, Document | None, DocumentChunk | None]],
        ] = {}
        evidence_rows = self.db.execute(
            select(WikiClaimEvidence, Document, DocumentChunk)
            .outerjoin(Document, Document.id == WikiClaimEvidence.document_id)
            .outerjoin(
                DocumentChunk,
                and_(
                    DocumentChunk.id == WikiClaimEvidence.chunk_id,
                    DocumentChunk.doc_id == WikiClaimEvidence.document_id,
                ),
            )
            .where(WikiClaimEvidence.owner_id == self.owner_id)
        ).all()
        for evidence, document, chunk in evidence_rows:
            evidence_by_claim.setdefault(evidence.claim_id, []).append((evidence, document, chunk))
        for claim in claims:
            valid_supports = 0
            current_support_quotes: list[str] = []
            for evidence, document, chunk in evidence_by_claim.get(claim.id, []):
                is_valid = bool(document and chunk and self.validator.evidence_row_is_current(evidence, document, chunk))
                if not is_valid:
                    issues.append(
                        WikiLintIssue(
                            code="STALE_EVIDENCE",
                            severity="error",
                            message="Beleg verweist nicht mehr auf den aktuellen OCR-Chunk.",
                            page_id=claim.page_id,
                            claim_id=claim.id,
                            evidence_id=evidence.id,
                        )
                    )
                elif evidence.support_role == "supports":
                    valid_supports += 1
                    current_support_quotes.append(evidence.quote)
            if claim.claim_type == "fact" and claim.status == "active" and valid_supports == 0:
                issues.append(
                    WikiLintIssue(
                        code="UNSUPPORTED_ACTIVE_FACT",
                        severity="critical",
                        message="Aktiver Fakten-Claim besitzt keinen aktuellen Beleg.",
                        page_id=claim.page_id,
                        claim_id=claim.id,
                    )
                )
                if fix:
                    claim.status = "stale"
                    claim.updated_at = datetime.now(timezone.utc)
                    fixed += 1
            elif claim.claim_type == "fact" and claim.status == "active" and not self.validator.fact_is_source_supported(
                text=claim.text,
                predicate=claim.predicate,
                object_text=claim.object_text,
                valid_from=claim.valid_from,
                quotes=current_support_quotes,
            ):
                issues.append(
                    WikiLintIssue(
                        code="CLAIM_NOT_ENTAILED_BY_SOURCE",
                        severity="critical",
                        message="Aktiver Fakten-Claim ist weder ein Originalzitat noch eine sichere strukturierte Ableitung.",
                        page_id=claim.page_id,
                        claim_id=claim.id,
                    )
                )
                if fix:
                    claim.status = "stale"
                    claim.updated_at = datetime.now(timezone.utc)
                    fixed += 1

        pages = list(self.db.execute(select(WikiPage).where(WikiPage.owner_id == self.owner_id)).scalars())
        pages_by_id = {page.id: page for page in pages}
        inbound_counts = dict(
            self.db.execute(
                select(WikiLink.to_page_id, func.count(WikiLink.id))
                .where(
                    WikiLink.owner_id == self.owner_id,
                    WikiLink.status == "active",
                )
                .group_by(WikiLink.to_page_id)
            ).all()
        )
        for page in pages:
            if page.current_revision_id is None:
                issues.append(
                    WikiLintIssue(
                        code="PAGE_WITHOUT_REVISION",
                        severity="warning",
                        message="Wissensseite besitzt noch keine Revision.",
                        page_id=page.id,
                    )
                )
            inbound = int(inbound_counts.get(page.id, 0))
            if page.kind != "source" and inbound == 0:
                issues.append(
                    WikiLintIssue(
                        code="ORPHAN_PAGE",
                        severity="info",
                        message="Wissensseite besitzt keine aktive eingehende Verknüpfung.",
                        page_id=page.id,
                    )
                )

        # Keep only the newest pending document proposal per type. The newest
        # item is rebound to the current immutable page revision; older review
        # items cannot be accidentally applied after a recompilation.
        pending_proposals = list(
            self.db.execute(
                select(WikiUpdateProposal)
                .where(
                    WikiUpdateProposal.owner_id == self.owner_id,
                    WikiUpdateProposal.status == "pending",
                    WikiUpdateProposal.source_document_id.isnot(None),
                    WikiUpdateProposal.page_id.isnot(None),
                )
                .order_by(WikiUpdateProposal.created_at.desc())
            ).scalars()
        )
        newest_by_source: set[tuple[uuid.UUID | None, str]] = set()
        for proposal in pending_proposals:
            key = (proposal.source_document_id, proposal.proposal_type)
            page = pages_by_id.get(proposal.page_id)
            if key not in newest_by_source and page is not None:
                newest_by_source.add(key)
                if proposal.base_revision_id != page.current_revision_id:
                    proposal.base_revision_id = page.current_revision_id
                continue
            proposal.status = "rejected"
            proposal.reviewed_at = datetime.now(timezone.utc)
            proposal.review_note = "Automatisch durch eine neuere Dokumentrevision ersetzt"
            issues.append(
                WikiLintIssue(
                    code="STALE_PROPOSAL",
                    severity="info",
                    message="Veralteter Wissensvorschlag wurde durch die neuere Dokumentrevision ersetzt.",
                    page_id=proposal.page_id,
                )
            )

        self._event("lint_completed", payload={"issues": len(issues), "fixed_claims": fixed})
        self.db.commit()
        return WikiLintResponse(
            checked_pages=len(pages),
            checked_claims=len(claims),
            fixed_claims=fixed,
            issues=issues,
        )

    def backfill(self, *, limit: int = 500) -> WikiBackfillResponse:
        documents = list(
            self.db.execute(
                select(Document)
                .where(
                    Document.owner_id == self.owner_id,
                    Document.is_deleted.is_(False),
                    Document.embedding_status == "done",
                )
                .order_by(Document.created_at.asc())
                .limit(max(1, min(limit, 5000)))
            ).scalars()
        )
        updated = review = failed = 0
        for document in documents:
            try:
                result = self.refresh_document(document.id, commit=True)
                updated += int(bool(result.get("updated")))
                review += int(result.get("review_proposals") or 0)
            except Exception:  # pragma: no cover - defensive per-document isolation
                failed += 1
                self.db.rollback()
                logger.exception("wiki backfill failed document_id=%s", document.id)
        return WikiBackfillResponse(
            processed=len(documents),
            updated=updated,
            review_proposals=review,
            failed=failed,
        )

    def overview(self) -> WikiOverviewResponse:
        pages = int(self.db.scalar(select(func.count()).select_from(WikiPage).where(WikiPage.owner_id == self.owner_id)) or 0)
        status_rows = dict(
            self.db.execute(
                select(WikiClaim.status, func.count(WikiClaim.id))
                .where(WikiClaim.owner_id == self.owner_id)
                .group_by(WikiClaim.status)
            ).all()
        )
        pending = int(
            self.db.scalar(
                select(func.count()).select_from(WikiUpdateProposal).where(
                    WikiUpdateProposal.owner_id == self.owner_id,
                    WikiUpdateProposal.status == "pending",
                )
            )
            or 0
        )
        source_total = int(
            self.db.scalar(
                select(func.count()).select_from(Document).where(
                    Document.owner_id == self.owner_id,
                    Document.is_deleted.is_(False),
                    Document.embedding_status == "done",
                )
            )
            or 0
        )
        coverage = int(
            self.db.scalar(
                select(func.count(func.distinct(Document.id)))
                .select_from(Document)
                .join(
                    WikiUpdateProposal,
                    and_(
                        WikiUpdateProposal.source_document_id == Document.id,
                        WikiUpdateProposal.owner_id == Document.owner_id,
                    ),
                )
                .where(
                    Document.owner_id == self.owner_id,
                    Document.is_deleted.is_(False),
                    Document.embedding_status == "done",
                    WikiUpdateProposal.proposal_type == "document_compile",
                    WikiUpdateProposal.status == "applied",
                    WikiUpdateProposal.schema_version == WIKI_SCHEMA_VERSION,
                )
            )
            or 0
        )
        return WikiOverviewResponse(
            pages=pages,
            active_claims=int(status_rows.get("active", 0)),
            review_claims=int(status_rows.get("needs_review", 0)),
            disputed_claims=int(status_rows.get("disputed", 0)),
            stale_claims=int(status_rows.get("stale", 0)),
            pending_proposals=pending,
            source_coverage=coverage,
            source_total=source_total,
        )
