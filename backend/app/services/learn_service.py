import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.models.learn import LearnCard, LearnCourse, LearnSession, LearnSheet
from app.schemas.learn import (
    LearnBoardResponse,
    LearnBoardSession,
    LearnCardCreate,
    LearnCardRead,
    LearnCardUpdate,
    LearnCourseCreate,
    LearnCourseRead,
    LearnCourseUpdate,
    LearnSessionCreate,
    LearnSessionRead,
    LearnSessionUpdate,
    LearnSheetCreate,
    LearnSheetRead,
    LearnSheetUpdate,
)

logger = logging.getLogger("papermind.learn")


class LearnService:
    """CRUD für die Container-Ebene des Lernbereichs (Kurs/Sitzung/Lernblatt).

    Owner-scoped; RLS erzwingt die Isolation zusätzlich auf DB-Ebene. Karten/
    Artefakte existieren noch nicht – ``card_count`` ist vorerst 0.
    """

    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    # --- Kurse -------------------------------------------------------------
    def _course_counts(self) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        sess_stmt = select(LearnSession.course_id, func.count(LearnSession.id))
        sheet_stmt = select(LearnSheet.course_id, func.count(LearnSheet.id))
        if self.owner_id is not None:
            sess_stmt = sess_stmt.where(LearnSession.owner_id == self.owner_id)
            sheet_stmt = sheet_stmt.where(LearnSheet.owner_id == self.owner_id)
        sess_stmt = sess_stmt.group_by(LearnSession.course_id)
        sheet_stmt = sheet_stmt.group_by(LearnSheet.course_id)
        sessions = {cid: n for cid, n in self.db.execute(sess_stmt).all()}
        sheets = {cid: n for cid, n in self.db.execute(sheet_stmt).all()}
        return sessions, sheets

    def list_courses(self) -> list[LearnCourseRead]:
        stmt = select(LearnCourse).order_by(
            LearnCourse.is_archived.asc(), LearnCourse.position.asc(), func.lower(LearnCourse.title).asc()
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCourse.owner_id == self.owner_id)
        courses = self.db.execute(stmt).scalars().all()
        sessions, sheets = self._course_counts()
        return [
            LearnCourseRead.model_validate(c, from_attributes=True).model_copy(
                update={"session_count": sessions.get(c.id, 0), "sheet_count": sheets.get(c.id, 0)}
            )
            for c in courses
        ]

    def get_course_or_404(self, course_id: uuid.UUID) -> LearnCourse:
        course = self.db.get(LearnCourse, course_id)
        if course is None or (self.owner_id is not None and course.owner_id != self.owner_id):
            raise NotFoundError("Course not found", details={"course_id": str(course_id)})
        return course

    def create_course(self, payload: LearnCourseCreate) -> LearnCourse:
        title = payload.title.strip()
        if not title:
            raise BadRequestError("Course title must not be empty")
        course = LearnCourse(
            owner_id=self.owner_id,
            title=title,
            module_key=payload.module_key,
            default_artifact_type=payload.default_artifact_type,
            has_script=payload.has_script,
            color=payload.color,
            position=self._next_course_position(),
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        logger.info("learn course created id=%s", course.id)
        return course

    def _next_course_position(self) -> int:
        stmt = select(func.coalesce(func.max(LearnCourse.position), -1) + 1)
        if self.owner_id is not None:
            stmt = stmt.where(LearnCourse.owner_id == self.owner_id)
        return int(self.db.execute(stmt).scalar_one())

    def update_course(self, course_id: uuid.UUID, payload: LearnCourseUpdate) -> LearnCourse:
        course = self.get_course_or_404(course_id)
        fields = payload.model_fields_set
        if "title" in fields and payload.title is not None:
            course.title = payload.title.strip()
        if "module_key" in fields:
            course.module_key = payload.module_key
        if "default_artifact_type" in fields and payload.default_artifact_type is not None:
            course.default_artifact_type = payload.default_artifact_type
        if "has_script" in fields and payload.has_script is not None:
            course.has_script = payload.has_script
        if "color" in fields:
            course.color = payload.color
        if "is_archived" in fields and payload.is_archived is not None:
            course.is_archived = payload.is_archived
        if "position" in fields and payload.position is not None:
            course.position = payload.position
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete_course(self, course_id: uuid.UUID) -> None:
        course = self.get_course_or_404(course_id)
        self.db.delete(course)
        self.db.commit()
        logger.info("learn course deleted id=%s", course_id)

    # --- Sitzungen ---------------------------------------------------------
    def list_sessions(self, course_id: uuid.UUID) -> list[LearnSessionRead]:
        self.get_course_or_404(course_id)
        stmt = (
            select(LearnSession)
            .where(LearnSession.course_id == course_id)
            .order_by(LearnSession.ordinal.desc(), LearnSession.session_date.desc().nullslast(), LearnSession.created_at.desc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnSession.owner_id == self.owner_id)
        sessions = self.db.execute(stmt).scalars().all()
        counts = self._sheet_counts_by_session(course_id)
        return [
            LearnSessionRead.model_validate(s, from_attributes=True).model_copy(
                update={"sheet_count": counts.get(s.id, 0)}
            )
            for s in sessions
        ]

    def _sheet_counts_by_session(self, course_id: uuid.UUID) -> dict[uuid.UUID, int]:
        stmt = (
            select(LearnSheet.session_id, func.count(LearnSheet.id))
            .where(LearnSheet.course_id == course_id, LearnSheet.session_id.is_not(None))
            .group_by(LearnSheet.session_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnSheet.owner_id == self.owner_id)
        return {sid: n for sid, n in self.db.execute(stmt).all()}

    def get_session_or_404(self, session_id: uuid.UUID) -> LearnSession:
        session = self.db.get(LearnSession, session_id)
        if session is None or (self.owner_id is not None and session.owner_id != self.owner_id):
            raise NotFoundError("Session not found", details={"session_id": str(session_id)})
        return session

    def create_session(self, course_id: uuid.UUID, payload: LearnSessionCreate) -> LearnSession:
        self.get_course_or_404(course_id)
        session = LearnSession(
            owner_id=self.owner_id,
            course_id=course_id,
            title=payload.title.strip(),
            session_date=payload.session_date,
            note_id=payload.note_id,
            ordinal=payload.ordinal,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info("learn session created id=%s course=%s", session.id, course_id)
        return session

    def update_session(self, session_id: uuid.UUID, payload: LearnSessionUpdate) -> LearnSession:
        session = self.get_session_or_404(session_id)
        fields = payload.model_fields_set
        if "title" in fields and payload.title is not None:
            session.title = payload.title.strip()
        if "session_date" in fields:
            session.session_date = payload.session_date
        if "note_id" in fields:
            session.note_id = payload.note_id
        if "ordinal" in fields and payload.ordinal is not None:
            session.ordinal = payload.ordinal
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: uuid.UUID) -> None:
        session = self.get_session_or_404(session_id)
        self.db.delete(session)
        self.db.commit()
        logger.info("learn session deleted id=%s", session_id)

    # --- Lernblätter -------------------------------------------------------
    def list_sheets(
        self, course_id: uuid.UUID | None = None, session_id: uuid.UUID | None = None
    ) -> list[LearnSheetRead]:
        stmt = select(LearnSheet).order_by(LearnSheet.position.asc(), LearnSheet.created_at.desc())
        if self.owner_id is not None:
            stmt = stmt.where(LearnSheet.owner_id == self.owner_id)
        if course_id is not None:
            stmt = stmt.where(LearnSheet.course_id == course_id)
        if session_id is not None:
            stmt = stmt.where(LearnSheet.session_id == session_id)
        sheets = self.db.execute(stmt).scalars().all()
        counts = self._card_counts_by_sheet([s.id for s in sheets])
        return [
            LearnSheetRead.model_validate(s, from_attributes=True).model_copy(
                update={"card_count": counts.get(s.id, 0)}
            )
            for s in sheets
        ]

    def _card_counts_by_sheet(self, sheet_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not sheet_ids:
            return {}
        stmt = (
            select(LearnCard.sheet_id, func.count(LearnCard.id))
            .where(LearnCard.sheet_id.in_(sheet_ids))
            .group_by(LearnCard.sheet_id)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        return {sid: n for sid, n in self.db.execute(stmt).all()}

    def get_sheet_or_404(self, sheet_id: uuid.UUID) -> LearnSheet:
        sheet = self.db.get(LearnSheet, sheet_id)
        if sheet is None or (self.owner_id is not None and sheet.owner_id != self.owner_id):
            raise NotFoundError("Sheet not found", details={"sheet_id": str(sheet_id)})
        return sheet

    def create_sheet(self, payload: LearnSheetCreate) -> LearnSheet:
        self.get_course_or_404(payload.course_id)
        if payload.session_id is not None:
            session = self.get_session_or_404(payload.session_id)
            if session.course_id != payload.course_id:
                raise BadRequestError("Session belongs to a different course")
        sheet = LearnSheet(
            owner_id=self.owner_id,
            course_id=payload.course_id,
            session_id=payload.session_id,
            title=payload.title.strip(),
            scope=payload.scope,
            status=payload.status,
            is_favorite=payload.is_favorite,
            structure=payload.structure or {},
            source_label=payload.source_label,
            position=self._next_sheet_position(payload.course_id),
        )
        self.db.add(sheet)
        self.db.commit()
        self.db.refresh(sheet)
        logger.info("learn sheet created id=%s course=%s", sheet.id, payload.course_id)
        return sheet

    def _next_sheet_position(self, course_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(LearnSheet.position), -1) + 1).where(
            LearnSheet.course_id == course_id
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnSheet.owner_id == self.owner_id)
        return int(self.db.execute(stmt).scalar_one())

    def update_sheet(self, sheet_id: uuid.UUID, payload: LearnSheetUpdate) -> LearnSheet:
        sheet = self.get_sheet_or_404(sheet_id)
        fields = payload.model_fields_set
        if "session_id" in fields:
            if payload.session_id is not None:
                session = self.get_session_or_404(payload.session_id)
                if session.course_id != sheet.course_id:
                    raise BadRequestError("Session belongs to a different course")
            sheet.session_id = payload.session_id
        if "title" in fields and payload.title is not None:
            sheet.title = payload.title.strip()
        if "scope" in fields and payload.scope is not None:
            sheet.scope = payload.scope
        if "status" in fields and payload.status is not None:
            sheet.status = payload.status
        if "is_favorite" in fields and payload.is_favorite is not None:
            sheet.is_favorite = payload.is_favorite
        if "structure" in fields and payload.structure is not None:
            sheet.structure = payload.structure
        if "source_label" in fields:
            sheet.source_label = payload.source_label
        if "position" in fields and payload.position is not None:
            sheet.position = payload.position
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

    def delete_sheet(self, sheet_id: uuid.UUID) -> None:
        sheet = self.get_sheet_or_404(sheet_id)
        self.db.delete(sheet)
        self.db.commit()
        logger.info("learn sheet deleted id=%s", sheet_id)

    # --- Board (Artboard 1a) ----------------------------------------------
    def get_board(self, course_id: uuid.UUID) -> LearnBoardResponse:
        course = self.get_course_or_404(course_id)
        course_read = LearnCourseRead.model_validate(course, from_attributes=True)

        sessions = self.list_sessions(course_id)
        all_sheets = self.list_sheets(course_id=course_id)
        by_session: dict[uuid.UUID, list[LearnSheetRead]] = {}
        loose: list[LearnSheetRead] = []
        for sheet in all_sheets:
            if sheet.session_id is None:
                loose.append(sheet)
            else:
                by_session.setdefault(sheet.session_id, []).append(sheet)

        board_sessions = [
            LearnBoardSession(
                id=s.id,
                title=s.title,
                session_date=s.session_date,
                ordinal=s.ordinal,
                sheets=by_session.get(s.id, []),
            )
            for s in sessions
        ]
        return LearnBoardResponse(course=course_read, sessions=board_sessions, loose_sheets=loose)

    # --- Karten ------------------------------------------------------------
    def list_cards(self, sheet_id: uuid.UUID) -> list[LearnCardRead]:
        self.get_sheet_or_404(sheet_id)
        stmt = (
            select(LearnCard)
            .where(LearnCard.sheet_id == sheet_id)
            .order_by(LearnCard.position.asc(), LearnCard.created_at.asc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        cards = self.db.execute(stmt).scalars().all()
        return [LearnCardRead.model_validate(c, from_attributes=True) for c in cards]

    def get_card_or_404(self, card_id: uuid.UUID) -> LearnCard:
        card = self.db.get(LearnCard, card_id)
        if card is None or (self.owner_id is not None and card.owner_id != self.owner_id):
            raise NotFoundError("Card not found", details={"card_id": str(card_id)})
        return card

    def _next_card_position(self, sheet_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(LearnCard.position), -1) + 1).where(
            LearnCard.sheet_id == sheet_id
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        return int(self.db.execute(stmt).scalar_one())

    def create_card(self, sheet_id: uuid.UUID, payload: LearnCardCreate) -> LearnCard:
        self.get_sheet_or_404(sheet_id)
        front = payload.front.strip()
        if not front:
            raise BadRequestError("Card front must not be empty")
        card = LearnCard(
            owner_id=self.owner_id,
            sheet_id=sheet_id,
            kind=payload.kind,
            front=front,
            back=(payload.back.strip() if payload.back and payload.back.strip() else None),
            position=self._next_card_position(sheet_id),
        )
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        logger.info("learn card created id=%s sheet=%s", card.id, sheet_id)
        return card

    def update_card(self, card_id: uuid.UUID, payload: LearnCardUpdate) -> LearnCard:
        card = self.get_card_or_404(card_id)
        fields = payload.model_fields_set
        if "kind" in fields and payload.kind is not None:
            card.kind = payload.kind
        if "front" in fields and payload.front is not None:
            card.front = payload.front.strip()
        if "back" in fields:
            card.back = payload.back.strip() if payload.back and payload.back.strip() else None
        if "position" in fields and payload.position is not None:
            card.position = payload.position
        self.db.commit()
        self.db.refresh(card)
        return card

    def delete_card(self, card_id: uuid.UUID) -> None:
        card = self.get_card_or_404(card_id)
        self.db.delete(card)
        self.db.commit()
        logger.info("learn card deleted id=%s", card_id)
