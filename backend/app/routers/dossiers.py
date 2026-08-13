import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.dossiers import (
    DossierBoardResponse,
    DossierCreateRequest,
    DossierDocumentsAddRequest,
    DossierDocumentsAddResponse,
    DossierGroupCreateRequest,
    DossierGroupOrderRequest,
    DossierGroupRead,
    DossierGroupUpdateRequest,
    DossierItemCreateRequest,
    DossierItemRead,
    DossierItemsBatchResponse,
    DossierItemsDeleteRequest,
    DossierItemsReorderRequest,
    DossierItemsRestoreRequest,
    DossierItemUpdateRequest,
    DossierListResponse,
    DossierRead,
    DossierUpdateRequest,
)
from app.services.dossiers import DossierService


router = APIRouter(prefix="/api/dossiers", tags=["Dossiers"])


@router.get("", response_model=DossierListResponse, summary="List manual dossiers")
def list_dossiers(
    include_archived: bool = False,
    q: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierListResponse:
    return DossierListResponse(
        items=DossierService(db, user.id).list_dossiers(include_archived=include_archived, q=q)
    )


@router.post(
    "",
    response_model=DossierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual dossier",
    responses={422: {"model": ErrorResponse}},
)
def create_dossier(
    payload: DossierCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierRead:
    service = DossierService(db, user.id)
    return service._dossier_model(service.create_dossier(payload))


@router.get(
    "/{dossier_id}",
    response_model=DossierRead,
    summary="Get dossier details",
    responses={404: {"model": ErrorResponse}},
)
def get_dossier(
    dossier_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierRead:
    service = DossierService(db, user.id)
    return service._dossier_model(service.get_dossier_or_404(dossier_id))


@router.patch(
    "/{dossier_id}",
    response_model=DossierRead,
    summary="Update dossier details and properties",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_dossier(
    dossier_id: uuid.UUID,
    payload: DossierUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierRead:
    service = DossierService(db, user.id)
    return service._dossier_model(service.update_dossier(dossier_id, payload))


@router.delete(
    "/{dossier_id}",
    response_model=OkResponse,
    summary="Delete a dossier without deleting documents",
    responses={404: {"model": ErrorResponse}},
)
def delete_dossier(
    dossier_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    DossierService(db, user.id).delete_dossier(dossier_id)
    return OkResponse(ok=True)


@router.post(
    "/{dossier_id}/duplicate",
    response_model=DossierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a dossier with its groups and items",
    responses={404: {"model": ErrorResponse}},
)
def duplicate_dossier(
    dossier_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierRead:
    service = DossierService(db, user.id)
    return service._dossier_model(service.duplicate_dossier(dossier_id))


@router.get(
    "/{dossier_id}/board",
    response_model=DossierBoardResponse,
    summary="Load the complete dossier light table",
    responses={404: {"model": ErrorResponse}},
)
def get_dossier_board(
    dossier_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierBoardResponse:
    dossier, groups, items = DossierService(db, user.id).board(dossier_id)
    return DossierBoardResponse(
        dossier=dossier,
        groups=[DossierGroupRead.model_validate(group, from_attributes=True) for group in groups],
        items=items,
    )


@router.post(
    "/{dossier_id}/groups",
    response_model=DossierGroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a dossier group",
)
def create_group(
    dossier_id: uuid.UUID,
    payload: DossierGroupCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierGroupRead:
    group = DossierService(db, user.id).create_group(dossier_id, payload)
    return DossierGroupRead.model_validate(group, from_attributes=True)


@router.patch(
    "/{dossier_id}/groups/{group_id}",
    response_model=DossierGroupRead,
    summary="Update a dossier group",
)
def update_group(
    dossier_id: uuid.UUID,
    group_id: uuid.UUID,
    payload: DossierGroupUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierGroupRead:
    group = DossierService(db, user.id).update_group(dossier_id, group_id, payload)
    return DossierGroupRead.model_validate(group, from_attributes=True)


@router.put(
    "/{dossier_id}/groups/order",
    response_model=list[DossierGroupRead],
    summary="Persist dossier group order",
)
def reorder_groups(
    dossier_id: uuid.UUID,
    payload: DossierGroupOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DossierGroupRead]:
    groups = DossierService(db, user.id).reorder_groups(dossier_id, payload.group_ids)
    return [DossierGroupRead.model_validate(group, from_attributes=True) for group in groups]


@router.delete(
    "/{dossier_id}/groups/{group_id}",
    response_model=OkResponse,
    summary="Delete group and move its contents to ungrouped",
)
def delete_group(
    dossier_id: uuid.UUID,
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    DossierService(db, user.id).delete_group(dossier_id, group_id)
    return OkResponse(ok=True)


@router.post(
    "/{dossier_id}/documents",
    response_model=DossierDocumentsAddResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add existing documents to a dossier",
)
def add_documents(
    dossier_id: uuid.UUID,
    payload: DossierDocumentsAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierDocumentsAddResponse:
    service = DossierService(db, user.id)
    items, skipped = service.add_documents(dossier_id, payload)
    return DossierDocumentsAddResponse(
        items=service.item_models(items),
        skipped_document_ids=skipped,
    )


@router.post(
    "/{dossier_id}/items",
    response_model=DossierItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note, link or document item",
)
def create_item(
    dossier_id: uuid.UUID,
    payload: DossierItemCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierItemRead:
    service = DossierService(db, user.id)
    return service.item_models([service.create_item(dossier_id, payload)])[0]


@router.patch(
    "/{dossier_id}/items/{item_id}",
    response_model=DossierItemRead,
    summary="Update a dossier item",
)
def update_item(
    dossier_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: DossierItemUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierItemRead:
    service = DossierService(db, user.id)
    return service.item_models([service.update_item(dossier_id, item_id, payload)])[0]


@router.put(
    "/{dossier_id}/items/order",
    response_model=list[DossierItemRead],
    summary="Move and reorder dossier items",
)
def reorder_items(
    dossier_id: uuid.UUID,
    payload: DossierItemsReorderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DossierItemRead]:
    service = DossierService(db, user.id)
    return service.item_models(service.reorder_items(dossier_id, payload))


@router.post(
    "/{dossier_id}/items/batch-delete",
    response_model=OkResponse,
    summary="Remove several dossier items atomically",
)
def delete_items(
    dossier_id: uuid.UUID,
    payload: DossierItemsDeleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    DossierService(db, user.id).delete_items(dossier_id, payload)
    return OkResponse(ok=True)


@router.post(
    "/{dossier_id}/items/batch-restore",
    response_model=DossierItemsBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Restore dossier items from an undo snapshot",
)
def restore_items(
    dossier_id: uuid.UUID,
    payload: DossierItemsRestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DossierItemsBatchResponse:
    service = DossierService(db, user.id)
    return DossierItemsBatchResponse(items=service.item_models(service.restore_items(dossier_id, payload)))


@router.delete(
    "/{dossier_id}/items/{item_id}",
    response_model=OkResponse,
    summary="Remove an item from the dossier",
)
def delete_item(
    dossier_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    DossierService(db, user.id).delete_item(dossier_id, item_id)
    return OkResponse(ok=True)
