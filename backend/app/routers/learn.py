import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.learn import (
    LearnBoardResponse,
    LearnCardCreate,
    LearnCardListResponse,
    LearnCardRead,
    LearnCardUpdate,
    LearnCourseCreate,
    LearnCourseListResponse,
    LearnCourseRead,
    LearnCourseUpdate,
    LearnSessionCreate,
    LearnSessionListResponse,
    LearnSessionRead,
    LearnSessionUpdate,
    LearnSheetCreate,
    LearnSheetListResponse,
    LearnSheetRead,
    LearnSheetUpdate,
)
from app.services.learn_service import LearnService

router = APIRouter(prefix="/api/learn", tags=["Learn"])


def _service(db: Session, user: User) -> LearnService:
    return LearnService(db, user.id)


# --- Kurse -----------------------------------------------------------------
@router.get("/courses", response_model=LearnCourseListResponse, summary="List courses")
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnCourseListResponse:
    return LearnCourseListResponse(items=_service(db, user).list_courses())


@router.post(
    "/courses",
    response_model=LearnCourseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a course",
    responses={422: {"model": ErrorResponse}},
)
def create_course(payload: LearnCourseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnCourseRead:
    return LearnCourseRead.model_validate(_service(db, user).create_course(payload), from_attributes=True)


@router.patch(
    "/courses/{course_id}",
    response_model=LearnCourseRead,
    summary="Update a course",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_course(
    course_id: uuid.UUID, payload: LearnCourseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnCourseRead:
    return LearnCourseRead.model_validate(_service(db, user).update_course(course_id, payload), from_attributes=True)


@router.delete(
    "/courses/{course_id}",
    response_model=OkResponse,
    summary="Delete a course",
    responses={404: {"model": ErrorResponse}},
)
def delete_course(course_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    _service(db, user).delete_course(course_id)
    return OkResponse(ok=True)


@router.get(
    "/courses/{course_id}/board",
    response_model=LearnBoardResponse,
    summary="Course board (sessions with their sheets) – Artboard 1a",
    responses={404: {"model": ErrorResponse}},
)
def get_board(course_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnBoardResponse:
    return _service(db, user).get_board(course_id)


# --- Sitzungen -------------------------------------------------------------
@router.get(
    "/courses/{course_id}/sessions",
    response_model=LearnSessionListResponse,
    summary="List sessions of a course",
    responses={404: {"model": ErrorResponse}},
)
def list_sessions(course_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnSessionListResponse:
    return LearnSessionListResponse(items=_service(db, user).list_sessions(course_id))


@router.post(
    "/courses/{course_id}/sessions",
    response_model=LearnSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_session(
    course_id: uuid.UUID, payload: LearnSessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnSessionRead:
    return LearnSessionRead.model_validate(_service(db, user).create_session(course_id, payload), from_attributes=True)


@router.patch(
    "/sessions/{session_id}",
    response_model=LearnSessionRead,
    summary="Update a session",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_session(
    session_id: uuid.UUID, payload: LearnSessionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnSessionRead:
    return LearnSessionRead.model_validate(_service(db, user).update_session(session_id, payload), from_attributes=True)


@router.delete(
    "/sessions/{session_id}",
    response_model=OkResponse,
    summary="Delete a session",
    responses={404: {"model": ErrorResponse}},
)
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    _service(db, user).delete_session(session_id)
    return OkResponse(ok=True)


# --- Lernblätter -----------------------------------------------------------
@router.get("/sheets", response_model=LearnSheetListResponse, summary="List sheets")
def list_sheets(
    course_id: uuid.UUID | None = Query(default=None),
    session_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LearnSheetListResponse:
    return LearnSheetListResponse(items=_service(db, user).list_sheets(course_id=course_id, session_id=session_id))


@router.post(
    "/sheets",
    response_model=LearnSheetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sheet",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_sheet(payload: LearnSheetCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnSheetRead:
    return LearnSheetRead.model_validate(_service(db, user).create_sheet(payload), from_attributes=True)


@router.patch(
    "/sheets/{sheet_id}",
    response_model=LearnSheetRead,
    summary="Update a sheet",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_sheet(
    sheet_id: uuid.UUID, payload: LearnSheetUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnSheetRead:
    return LearnSheetRead.model_validate(_service(db, user).update_sheet(sheet_id, payload), from_attributes=True)


@router.delete(
    "/sheets/{sheet_id}",
    response_model=OkResponse,
    summary="Delete a sheet",
    responses={404: {"model": ErrorResponse}},
)
def delete_sheet(sheet_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    _service(db, user).delete_sheet(sheet_id)
    return OkResponse(ok=True)


# --- Karten ----------------------------------------------------------------
@router.get(
    "/sheets/{sheet_id}/cards",
    response_model=LearnCardListResponse,
    summary="List cards of a sheet",
    responses={404: {"model": ErrorResponse}},
)
def list_cards(sheet_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> LearnCardListResponse:
    return LearnCardListResponse(items=_service(db, user).list_cards(sheet_id))


@router.post(
    "/sheets/{sheet_id}/cards",
    response_model=LearnCardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a card",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_card(
    sheet_id: uuid.UUID, payload: LearnCardCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnCardRead:
    return LearnCardRead.model_validate(_service(db, user).create_card(sheet_id, payload), from_attributes=True)


@router.patch(
    "/cards/{card_id}",
    response_model=LearnCardRead,
    summary="Update a card",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_card(
    card_id: uuid.UUID, payload: LearnCardUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LearnCardRead:
    return LearnCardRead.model_validate(_service(db, user).update_card(card_id, payload), from_attributes=True)


@router.delete(
    "/cards/{card_id}",
    response_model=OkResponse,
    summary="Delete a card",
    responses={404: {"model": ErrorResponse}},
)
def delete_card(card_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    _service(db, user).delete_card(card_id)
    return OkResponse(ok=True)
