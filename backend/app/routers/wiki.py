import uuid

from fastapi import APIRouter, Depends, Query, status as http_status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.wiki import (
    WikiBackfillControlRequest,
    WikiBackfillRunRead,
    WikiCaptureAnswerRequest,
    WikiClaimCorrectionRequest,
    WikiClaimRetractRequest,
    WikiLintResponse,
    WikiOverviewResponse,
    WikiPageDetail,
    WikiPageKind,
    WikiPageListResponse,
    WikiPageStatus,
    WikiProposalListResponse,
    WikiProposalRead,
    WikiProposalReviewRequest,
    WikiRevisionRead,
)
from app.services.wiki import WikiService
from app.services.wiki_backfill import WikiBackfillService


router = APIRouter(prefix="/api/wiki", tags=["Wiki"])


@router.get("/overview", response_model=WikiOverviewResponse, summary="LLM-wiki trust and coverage overview")
def overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiOverviewResponse:
    return WikiService(db, user.id).overview()


@router.get("/pages", response_model=WikiPageListResponse, summary="List current wiki pages")
def list_pages(
    q: str | None = Query(default=None, max_length=1000),
    kind: WikiPageKind | None = None,
    status: WikiPageStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiPageListResponse:
    return WikiService(db, user.id).list_pages(
        q=q,
        kind=kind.value if kind else None,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )


@router.get("/proposals", response_model=WikiProposalListResponse, summary="List reviewable wiki updates")
def list_proposals(
    status: str | None = Query(default="pending", max_length=24),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiProposalListResponse:
    return WikiService(db, user.id).list_proposals(status=status, limit=limit, offset=offset)


@router.post(
    "/proposals/{proposal_id}/review",
    response_model=WikiProposalRead,
    summary="Accept or reject a wiki update proposal",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def review_proposal(
    proposal_id: uuid.UUID,
    payload: WikiProposalReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiProposalRead:
    return WikiService(db, user.id).review_proposal(proposal_id, payload, reviewer_id=user.id)


@router.post("/capture-answer", response_model=WikiProposalRead, summary="Propose a chat answer for durable knowledge")
def capture_answer(
    payload: WikiCaptureAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiProposalRead:
    return WikiService(db, user.id).capture_chat_answer(payload)


@router.post("/lint", response_model=WikiLintResponse, summary="Validate citations, staleness and wiki structure")
def lint_wiki(
    fix: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiLintResponse:
    return WikiService(db, user.id).lint(fix=fix)


@router.post(
    "/backfill",
    response_model=WikiBackfillRunRead,
    status_code=http_status.HTTP_202_ACCEPTED,
    summary="Queue a resumable wiki backfill",
)
def backfill_wiki(
    batch_size: int = Query(default=1, ge=1, le=50),
    document_limit: int | None = Query(default=None, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiBackfillRunRead:
    run = WikiBackfillService(db, user.id).enqueue(
        batch_size=batch_size,
        document_limit=document_limit,
    )
    return WikiBackfillRunRead.model_validate(run, from_attributes=True)


@router.get("/backfill/status", response_model=WikiBackfillRunRead | None, summary="Get latest wiki backfill progress")
def backfill_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiBackfillRunRead | None:
    run = WikiBackfillService(db, user.id).latest()
    return WikiBackfillRunRead.model_validate(run, from_attributes=True) if run else None


@router.post(
    "/backfill/{run_id}/control",
    response_model=WikiBackfillRunRead,
    summary="Pause, resume or cancel a wiki backfill",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def control_backfill(
    run_id: uuid.UUID,
    payload: WikiBackfillControlRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiBackfillRunRead:
    run = WikiBackfillService(db, user.id).control(run_id, action=payload.action)
    return WikiBackfillRunRead.model_validate(run, from_attributes=True)


@router.post("/documents/{document_id}/refresh", response_model=dict, summary="Recompile one document wiki source")
def refresh_document_wiki(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return WikiService(db, user.id).refresh_document(document_id)


@router.post(
    "/claims/{claim_id}/correct",
    response_model=WikiPageDetail,
    summary="Correct a claim by creating a new immutable revision",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def correct_claim(
    claim_id: uuid.UUID,
    payload: WikiClaimCorrectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiPageDetail:
    return WikiService(db, user.id).correct_claim(claim_id, payload)


@router.post(
    "/claims/{claim_id}/retract",
    response_model=WikiPageDetail,
    summary="Retract a claim by creating a new immutable revision",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def retract_claim(
    claim_id: uuid.UUID,
    payload: WikiClaimRetractRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiPageDetail:
    return WikiService(db, user.id).retract_claim(claim_id, payload)


@router.get("/pages/{page_id}", response_model=WikiPageDetail, summary="Get a wiki page with claims and sources")
def get_page(
    page_id: uuid.UUID,
    include_history: bool = Query(default=False),
    claim_limit: int = Query(default=100, ge=1, le=500),
    claim_offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WikiPageDetail:
    return WikiService(db, user.id).get_page_detail(
        page_id,
        include_history=include_history,
        claim_limit=claim_limit,
        claim_offset=claim_offset,
    )


@router.get("/pages/{page_id}/revisions", response_model=list[WikiRevisionRead], summary="List immutable page revisions")
def list_revisions(
    page_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WikiRevisionRead]:
    return WikiService(db, user.id).list_revisions(page_id)
