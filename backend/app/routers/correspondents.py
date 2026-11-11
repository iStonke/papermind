import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import CountResponse, ErrorResponse, OkResponse
from app.schemas.correspondents import (
    CorrespondentAliasCreateRequest,
    CorrespondentCreateRequest,
    CorrespondentListResponse,
    CorrespondentMatcherCreateRequest,
    CorrespondentMergeRequest,
    CorrespondentMergeResponse,
    CorrespondentProfileRead,
    CorrespondentRead,
    CorrespondentRefinementResponse,
    CorrespondentRelationCreateRequest,
    CorrespondentRelationRead,
    CorrespondentReviewIgnoreRequest,
    CorrespondentUpdateRequest,
    UnresolvedCorrespondentReportResponse,
)
from app.services.correspondent_backfill import CorrespondentBackfillService
from app.services.correspondents import CorrespondentService
from app.services.documents import DocumentService

router = APIRouter(prefix="/api/correspondents", tags=["Correspondents"])


@router.get(
    "",
    response_model=CorrespondentListResponse,
    summary="List correspondents",
)
def list_correspondents(
    include_count: bool = Query(default=False, description="Include usage_count for each correspondent"),
    kind: str | None = Query(default=None, description="Filter by kind: organization | person | collection"),
    parent_id: uuid.UUID | None = Query(default=None, description="Filter by parent organization"),
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentListResponse:
    service = CorrespondentService(db, user.id)
    items = service.list_correspondents(include_count=include_count, kind=kind, parent_id=parent_id)
    return CorrespondentListResponse(
        items=[CorrespondentRead.model_validate(item, from_attributes=True) for item in items]
    )


@router.post(
    "",
    response_model=CorrespondentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a correspondent",
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_correspondent(payload: CorrespondentCreateRequest, db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user)) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.create_correspondent(payload), from_attributes=True)


@router.get(
    "/unresolved",
    response_model=UnresolvedCorrespondentReportResponse,
    summary="Report documents without a correspondent",
)
def report_unresolved_correspondents(
    limit: int = Query(default=200, ge=1, le=1000),
    include_deleted: bool = Query(default=False),
    excerpt_chars: int = Query(default=300, ge=0, le=2000),
    hidden: bool = Query(default=False, description="Bewusst ohne Korrespondent belassene Dokumente liefern"),
    suggest: bool = Query(default=False, description="Vorschlag aus vorhandenen Korrespondenten und ähnliche Kandidaten mitliefern"),
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> UnresolvedCorrespondentReportResponse:
    service = CorrespondentBackfillService(db, user.id)
    report = service.unresolved_report(
        limit=limit,
        include_deleted=include_deleted,
        excerpt_chars=excerpt_chars,
        hidden=hidden,
        suggest=suggest,
    )
    return UnresolvedCorrespondentReportResponse.model_validate(report.to_dict())


@router.post(
    "/unresolved/{document_id}/ignore",
    response_model=OkResponse,
    summary="Mark an unresolved document as intentionally without correspondent",
    responses={404: {"model": ErrorResponse}},
)
def ignore_unresolved_correspondent(
    document_id: uuid.UUID,
    payload: CorrespondentReviewIgnoreRequest,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> OkResponse:
    service = DocumentService(db, user.id)
    document = service.get_document_or_404(document_id)
    flags = dict(document.flags or {})
    flags["correspondent_review"] = "ignored"
    if payload.reason:
        flags["correspondent_review_reason"] = payload.reason
    else:
        flags.pop("correspondent_review_reason", None)
    document.flags = flags
    db.commit()
    return OkResponse()


@router.delete(
    "/unresolved/{document_id}/ignore",
    response_model=OkResponse,
    summary="Bring a document marked as without correspondent back to the open list",
    responses={404: {"model": ErrorResponse}},
)
def restore_unresolved_correspondent(
    document_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> OkResponse:
    document = DocumentService(db, user.id).get_document_or_404(document_id)
    flags = dict(document.flags or {})
    flags.pop("correspondent_review", None)
    flags.pop("correspondent_review_reason", None)
    document.flags = flags
    db.commit()
    return OkResponse()


@router.get(
    "/collection-documents",
    response_model=UnresolvedCorrespondentReportResponse,
    summary="Documents assigned directly to a collection (candidates for a more specific correspondent)",
)
def report_collection_documents(
    limit: int = Query(default=200, ge=1, le=1000),
    excerpt_chars: int = Query(default=0, ge=0, le=2000),
    hidden: bool = Query(default=False, description="Bewusst bei der Sammlung belassene Dokumente liefern"),
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> UnresolvedCorrespondentReportResponse:
    report = CorrespondentBackfillService(db, user.id).collection_report(limit=limit, excerpt_chars=excerpt_chars, hidden=hidden)
    return UnresolvedCorrespondentReportResponse.model_validate(report.to_dict())


@router.post(
    "/collection-documents/{document_id}/keep",
    response_model=OkResponse,
    summary="Keep a document deliberately with its collection",
    responses={404: {"model": ErrorResponse}},
)
def keep_collection_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> OkResponse:
    document = DocumentService(db, user.id).get_document_or_404(document_id)
    document.flags = {**(document.flags or {}), "collection_review": "kept"}
    db.commit()
    return OkResponse()


@router.delete(
    "/collection-documents/{document_id}/keep",
    response_model=OkResponse,
    summary="Bring a document kept with its collection back to the review list",
    responses={404: {"model": ErrorResponse}},
)
def restore_collection_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> OkResponse:
    document = DocumentService(db, user.id).get_document_or_404(document_id)
    flags = dict(document.flags or {})
    flags.pop("collection_review", None)
    document.flags = flags
    db.commit()
    return OkResponse()


@router.get(
    "/{correspondent_id}/profile",
    response_model=CorrespondentProfileRead,
    summary="Profile figures of a correspondent (organizations include their persons)",
    responses={404: {"model": ErrorResponse}},
)
def get_correspondent_profile(
    correspondent_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentProfileRead:
    return CorrespondentService(db, user.id).get_profile(correspondent_id)


@router.patch(
    "/{correspondent_id}",
    response_model=CorrespondentRead,
    summary="Update a correspondent",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_correspondent(
    correspondent_id: uuid.UUID,
    payload: CorrespondentUpdateRequest,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.update_correspondent(correspondent_id, payload), from_attributes=True)


@router.delete(
    "/{correspondent_id}",
    response_model=OkResponse,
    summary="Delete an unused correspondent",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def delete_correspondent(correspondent_id: uuid.UUID, db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user)) -> OkResponse:
    service = CorrespondentService(db, user.id)
    service.delete_correspondent(correspondent_id)
    return OkResponse()


@router.get(
    "/{correspondent_id}/refinements",
    response_model=CorrespondentRefinementResponse,
    summary="More specific members of a correspondent for one document",
    responses={404: {"model": ErrorResponse}},
)
def get_correspondent_refinements(
    correspondent_id: uuid.UUID,
    document_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db, scope="function"),
    user: User = Depends(get_current_user),
) -> CorrespondentRefinementResponse:
    items = CorrespondentService(db, user.id).refinement_suggestions(correspondent_id, document_id)
    return CorrespondentRefinementResponse(items=items)


@router.post(
    "/{correspondent_id}/merge",
    response_model=CorrespondentMergeResponse,
    summary="Merge another correspondent into this one",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def merge_correspondents(
    correspondent_id: uuid.UUID,
    payload: CorrespondentMergeRequest,
    db: Session = Depends(get_db, scope="function"),
    user: User = Depends(get_current_user),
) -> CorrespondentMergeResponse:
    target, counts = CorrespondentService(db, user.id).merge_correspondents(correspondent_id, payload.source_id)
    return CorrespondentMergeResponse(
        correspondent=CorrespondentRead.model_validate(target, from_attributes=True),
        documents=counts.documents,
        aliases=counts.aliases,
        matchers=counts.matchers,
        relations=counts.relations,
        members=counts.members,
        notes=counts.notes,
    )


@router.post(
    "/{correspondent_id}/unlink-documents",
    response_model=CountResponse,
    summary="Remove all document assignments from a correspondent",
    responses={404: {"model": ErrorResponse}},
)
def unlink_correspondent_documents(
    correspondent_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"),
    user: User = Depends(get_current_user),
) -> CountResponse:
    service = CorrespondentService(db, user.id)
    return CountResponse(count=service.unlink_documents(correspondent_id))


@router.post(
    "/{correspondent_id}/aliases",
    response_model=CorrespondentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an alias to a correspondent",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def add_correspondent_alias(
    correspondent_id: uuid.UUID,
    payload: CorrespondentAliasCreateRequest,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.add_alias(correspondent_id, payload.alias), from_attributes=True)


@router.delete(
    "/{correspondent_id}/aliases/{alias_id}",
    response_model=CorrespondentRead,
    summary="Delete an alias from a correspondent",
    responses={404: {"model": ErrorResponse}},
)
def delete_correspondent_alias(
    correspondent_id: uuid.UUID,
    alias_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.delete_alias(correspondent_id, alias_id), from_attributes=True)


@router.post(
    "/{correspondent_id}/matchers",
    response_model=CorrespondentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a matcher to a correspondent",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def add_correspondent_matcher(
    correspondent_id: uuid.UUID,
    payload: CorrespondentMatcherCreateRequest,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.add_matcher(correspondent_id, payload), from_attributes=True)


@router.post(
    "/{correspondent_id}/relations",
    response_model=CorrespondentRelationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a correspondent (predecessor, successor, acts for)",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def add_correspondent_relation(
    correspondent_id: uuid.UUID,
    payload: CorrespondentRelationCreateRequest,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRelationRead:
    return CorrespondentService(db, user.id).add_relation(correspondent_id, payload)


@router.delete(
    "/{correspondent_id}/relations/{relation_id}",
    response_model=OkResponse,
    summary="Remove a connection between correspondents",
    responses={404: {"model": ErrorResponse}},
)
def delete_correspondent_relation(
    correspondent_id: uuid.UUID,
    relation_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> OkResponse:
    CorrespondentService(db, user.id).delete_relation(correspondent_id, relation_id)
    return OkResponse()


@router.delete(
    "/{correspondent_id}/matchers/{matcher_id}",
    response_model=CorrespondentRead,
    summary="Delete a matcher from a correspondent",
    responses={404: {"model": ErrorResponse}},
)
def delete_correspondent_matcher(
    correspondent_id: uuid.UUID,
    matcher_id: uuid.UUID,
    db: Session = Depends(get_db, scope="function"), user: User = Depends(get_current_user),
) -> CorrespondentRead:
    service = CorrespondentService(db, user.id)
    return CorrespondentRead.model_validate(service.delete_matcher(correspondent_id, matcher_id), from_attributes=True)
