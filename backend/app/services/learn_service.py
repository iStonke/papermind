import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.models.learn import LearnCard, LearnCourse, LearnMarker, LearnRun, LearnSession, LearnSheet
from app.models.note import Note
from app.schemas.learn import (
    LearnBoardResponse,
    LearnBoardSession,
    LearnCardCreate,
    LearnCardRead,
    LearnCardUpdate,
    LearnProficiency,
    LearnRunCreate,
    LearnRunRead,
    LearnRunUpdate,
    LearnMarkerPromote,
    LearnMarkerRead,
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

    def _course_proficiency(self) -> dict[uuid.UUID, LearnProficiency]:
        """Lernstand-Verteilung der Karten je Kurs (Karte→Blatt→Kurs)."""
        stmt = (
            select(LearnSheet.course_id, LearnCard.status, func.count(LearnCard.id))
            .join(LearnSheet, LearnSheet.id == LearnCard.sheet_id)
            .group_by(LearnSheet.course_id, LearnCard.status)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        out: dict[uuid.UUID, LearnProficiency] = {}
        for course_id, status, n in self.db.execute(stmt).all():
            prof = out.setdefault(course_id, LearnProficiency())
            self._apply_status_count(prof, status, n)
        return out

    @staticmethod
    def _apply_status_count(prof: LearnProficiency, status: str, n: int) -> None:
        if status in ("open", "weak", "medium", "strong"):
            setattr(prof, status, getattr(prof, status) + n)
        else:
            prof.open += n
        prof.total += n

    def list_courses(self) -> list[LearnCourseRead]:
        stmt = select(LearnCourse).order_by(
            LearnCourse.is_archived.asc(), LearnCourse.position.asc(), func.lower(LearnCourse.title).asc()
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCourse.owner_id == self.owner_id)
        courses = self.db.execute(stmt).scalars().all()
        sessions, sheets = self._course_counts()
        prof = self._course_proficiency()
        return [
            LearnCourseRead.model_validate(c, from_attributes=True).model_copy(
                update={
                    "session_count": sessions.get(c.id, 0),
                    "sheet_count": sheets.get(c.id, 0),
                    "card_count": prof.get(c.id, LearnProficiency()).total,
                    "proficiency": prof.get(c.id, LearnProficiency()),
                }
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
            # Eine Notiz gehört zu höchstens einer Sitzung: vorherige Kopplung lösen.
            if payload.note_id is not None:
                self._unbind_note_from_other_sessions(payload.note_id, keep_session_id=session.id)
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
        sheet_ids = [s.id for s in sheets]
        counts = self._card_counts_by_sheet(sheet_ids)
        learnable_counts = self._learnable_card_counts_by_sheet(sheet_ids)
        prof = self._sheet_proficiency(sheet_ids)
        kinds = self._sheet_kind_summary(sheet_ids)
        return [
            LearnSheetRead.model_validate(s, from_attributes=True).model_copy(
                update={
                    "card_count": counts.get(s.id, 0),
                    "learnable_card_count": learnable_counts.get(s.id, 0),
                    "proficiency": prof.get(s.id, LearnProficiency()),
                    "kind_summary": kinds.get(s.id),
                }
            )
            for s in sheets
        ]

    def _sheet_kind_summary(self, sheet_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Dominanter Kartentyp je Blatt: der einzige Typ, sonst 'gemischt'."""
        if not sheet_ids:
            return {}
        stmt = (
            select(LearnCard.sheet_id, LearnCard.kind, func.count(LearnCard.id))
            .where(LearnCard.sheet_id.in_(sheet_ids))
            .group_by(LearnCard.sheet_id, LearnCard.kind)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        kinds_by_sheet: dict[uuid.UUID, set[str]] = {}
        for sheet_id, kind, _n in self.db.execute(stmt).all():
            kinds_by_sheet.setdefault(sheet_id, set()).add(kind)
        return {sid: (next(iter(ks)) if len(ks) == 1 else "gemischt") for sid, ks in kinds_by_sheet.items()}

    def _sheet_proficiency(self, sheet_ids: list[uuid.UUID]) -> dict[uuid.UUID, LearnProficiency]:
        if not sheet_ids:
            return {}
        stmt = (
            select(LearnCard.sheet_id, LearnCard.status, func.count(LearnCard.id))
            .where(LearnCard.sheet_id.in_(sheet_ids))
            .group_by(LearnCard.sheet_id, LearnCard.status)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnCard.owner_id == self.owner_id)
        out: dict[uuid.UUID, LearnProficiency] = {}
        for sheet_id, status, n in self.db.execute(stmt).all():
            self._apply_status_count(out.setdefault(sheet_id, LearnProficiency()), status, n)
        return out

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

    def _learnable_card_counts_by_sheet(self, sheet_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not sheet_ids:
            return {}
        stmt = (
            select(LearnCard.sheet_id, func.count(LearnCard.id))
            .where(
                LearnCard.sheet_id.in_(sheet_ids),
                func.length(func.trim(LearnCard.front)) > 0,
                LearnCard.back.is_not(None),
                func.length(func.trim(LearnCard.back)) > 0,
            )
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
        if "status" in fields and payload.status is not None:
            card.status = payload.status
        self.db.commit()
        self.db.refresh(card)
        return card

    def review_card(self, card_id: uuid.UUID, status: str) -> LearnCard:
        """Lernstand einer Karte aus der Selbsteinschätzung setzen."""
        card = self.get_card_or_404(card_id)
        card.status = status
        card.last_reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(card)
        return card

    def delete_card(self, card_id: uuid.UUID) -> None:
        card = self.get_card_or_404(card_id)
        self.db.delete(card)
        self.db.commit()
        logger.info("learn card deleted id=%s", card_id)

    # --- Lerndurchläufe ----------------------------------------------------
    def list_runs(self, course_id: uuid.UUID, limit: int = 20) -> list[LearnRunRead]:
        self.get_course_or_404(course_id)
        stmt = (
            select(LearnRun, LearnSheet.title)
            .outerjoin(LearnSheet, LearnSheet.id == LearnRun.sheet_id)
            .where(LearnRun.course_id == course_id)
            .order_by(LearnRun.started_at.desc())
            .limit(limit)
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnRun.owner_id == self.owner_id)
        return [
            LearnRunRead.model_validate(run, from_attributes=True).model_copy(update={"sheet_title": sheet_title})
            for run, sheet_title in self.db.execute(stmt).all()
        ]

    def get_run_or_404(self, run_id: uuid.UUID) -> LearnRun:
        run = self.db.get(LearnRun, run_id)
        if run is None or (self.owner_id is not None and run.owner_id != self.owner_id):
            raise NotFoundError("Learning run not found", details={"run_id": str(run_id)})
        return run

    def create_run(self, course_id: uuid.UUID, payload: LearnRunCreate) -> LearnRunRead:
        self.get_course_or_404(course_id)
        sheet_title = None
        if payload.sheet_id is not None:
            sheet = self.get_sheet_or_404(payload.sheet_id)
            if sheet.course_id != course_id:
                raise BadRequestError("Sheet belongs to a different course")
            sheet_title = sheet.title
        if payload.scope == "sheet" and payload.sheet_id is None:
            raise BadRequestError("Sheet runs require sheet_id")
        run = LearnRun(
            owner_id=self.owner_id,
            course_id=course_id,
            sheet_id=payload.sheet_id,
            scope=payload.scope,
            total_cards=payload.total_cards,
            started_at=payload.started_at or datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info("learn run created id=%s course=%s", run.id, course_id)
        return LearnRunRead.model_validate(run, from_attributes=True).model_copy(
            update={"sheet_title": sheet_title}
        )

    def update_run(self, run_id: uuid.UUID, payload: LearnRunUpdate) -> LearnRunRead:
        run = self.get_run_or_404(run_id)
        if payload.weak_count + payload.medium_count + payload.strong_count != payload.assessed_cards:
            raise BadRequestError("Assessment counts must equal assessed_cards")
        if payload.assessed_cards > run.total_cards:
            raise BadRequestError("assessed_cards exceeds total_cards")
        run.assessed_cards = payload.assessed_cards
        run.weak_count = payload.weak_count
        run.medium_count = payload.medium_count
        run.strong_count = payload.strong_count
        run.completed_at = payload.completed_at
        self.db.commit()
        self.db.refresh(run)
        sheet_title = None
        if run.sheet_id is not None:
            sheet = self.db.get(LearnSheet, run.sheet_id)
            sheet_title = sheet.title if sheet is not None else None
        return LearnRunRead.model_validate(run, from_attributes=True).model_copy(
            update={"sheet_title": sheet_title}
        )

    def delete_run(self, run_id: uuid.UUID) -> None:
        run = self.get_run_or_404(run_id)
        self.db.delete(run)
        self.db.commit()
        logger.info("learn run deleted id=%s", run_id)

    # --- Marker (aus Notizen) ---------------------------------------------
    def _unbind_note_from_other_sessions(
        self, note_id: uuid.UUID, keep_session_id: uuid.UUID | None = None
    ) -> None:
        """Löst die Notiz von allen Sitzungen außer ``keep_session_id`` (1 Notiz ↔ 1 Sitzung)."""
        stmt = select(LearnSession).where(LearnSession.note_id == note_id)
        if self.owner_id is not None:
            stmt = stmt.where(LearnSession.owner_id == self.owner_id)
        if keep_session_id is not None:
            stmt = stmt.where(LearnSession.id != keep_session_id)
        for other in self.db.execute(stmt).scalars().all():
            other.note_id = None

    def list_markers(
        self, note_id: uuid.UUID | None = None, open_only: bool = False
    ) -> list[LearnMarkerRead]:
        stmt = (
            select(LearnMarker, Note.title)
            .join(Note, Note.id == LearnMarker.note_id)
            .order_by(Note.updated_at.desc(), LearnMarker.position.asc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnMarker.owner_id == self.owner_id)
        if note_id is not None:
            stmt = stmt.where(LearnMarker.note_id == note_id)
        rows = self.db.execute(stmt).all()

        # Eine Markierung ist erst abgeschlossen, wenn die zugehörige Karte
        # Vorder- UND Rückseite enthält. Unvollständige Karten bleiben als
        # Nachbereitung sichtbar und werden samt Kurszuordnung zurückgegeben.
        card_stmt = (
            select(LearnCard, LearnSheet.course_id, LearnCourse.title)
            .join(LearnSheet, LearnSheet.id == LearnCard.sheet_id)
            .join(LearnCourse, LearnCourse.id == LearnSheet.course_id)
            .where(LearnCard.source_note_id.is_not(None))
            .order_by(LearnCard.created_at.desc())
        )
        if self.owner_id is not None:
            card_stmt = card_stmt.where(LearnCard.owner_id == self.owner_id)
        cards_by_marker: dict[tuple[uuid.UUID, str], list[tuple[LearnCard, uuid.UUID, str]]] = {}
        for card, course_id, course_title in self.db.execute(card_stmt).all():
            cards_by_marker.setdefault((card.source_note_id, card.source_pm_id), []).append(
                (card, course_id, course_title)
            )

        items: list[LearnMarkerRead] = []
        for marker, title in rows:
            linked_cards = cards_by_marker.get((marker.note_id, marker.node_pm_id), [])
            has_card = bool(linked_cards)
            has_complete_card = any(
                bool(card.front.strip() and card.back and card.back.strip())
                for card, _course_id, _course_title in linked_cards
            )
            if open_only and has_complete_card:
                continue
            update = {"note_title": title, "has_card": has_card}
            if linked_cards and not has_complete_card:
                draft, course_id, course_title = linked_cards[0]
                update.update(
                    {
                        "course_id": course_id,
                        "course_title": course_title,
                        "draft_card_id": draft.id,
                        "draft_sheet_id": draft.sheet_id,
                        "draft_kind": draft.kind,
                        "draft_front": draft.front,
                        "draft_back": draft.back,
                    }
                )
            items.append(
                LearnMarkerRead.model_validate(marker, from_attributes=True).model_copy(update=update)
            )
        return items

    def get_marker_or_404(self, note_id: uuid.UUID, node_pm_id: str) -> LearnMarker:
        stmt = select(LearnMarker).where(
            LearnMarker.note_id == note_id, LearnMarker.node_pm_id == node_pm_id
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnMarker.owner_id == self.owner_id)
        marker = self.db.execute(stmt).scalars().first()
        if marker is None:
            raise NotFoundError(
                "Marker not found", details={"note_id": str(note_id), "node_pm_id": node_pm_id}
            )
        return marker

    def _find_or_create_session_sheet(self, session: LearnSession) -> LearnSheet:
        """Sitzungs-Lernblatt für die Nachbereitung finden oder anlegen."""
        stmt = (
            select(LearnSheet)
            .where(LearnSheet.session_id == session.id, LearnSheet.scope == "session")
            .order_by(LearnSheet.position.asc(), LearnSheet.created_at.asc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnSheet.owner_id == self.owner_id)
        sheet = self.db.execute(stmt).scalars().first()
        if sheet is not None:
            return sheet
        sheet = LearnSheet(
            owner_id=self.owner_id,
            course_id=session.course_id,
            session_id=session.id,
            title=session.title,
            scope="session",
            status="in_progress",
            position=self._next_sheet_position(session.course_id),
        )
        self.db.add(sheet)
        self.db.flush()
        return sheet

    def _find_or_create_course_sheet(self, course_id: uuid.UUID) -> LearnSheet:
        """Themenübergreifendes „Nachbereitung"-Blatt eines Kurses finden oder anlegen."""
        title = "Nachbereitung"
        stmt = (
            select(LearnSheet)
            .where(
                LearnSheet.course_id == course_id,
                LearnSheet.session_id.is_(None),
                LearnSheet.title == title,
            )
            .order_by(LearnSheet.position.asc(), LearnSheet.created_at.asc())
        )
        if self.owner_id is not None:
            stmt = stmt.where(LearnSheet.owner_id == self.owner_id)
        sheet = self.db.execute(stmt).scalars().first()
        if sheet is not None:
            return sheet
        sheet = LearnSheet(
            owner_id=self.owner_id,
            course_id=course_id,
            session_id=None,
            title=title,
            scope="topic",
            status="in_progress",
            position=self._next_sheet_position(course_id),
        )
        self.db.add(sheet)
        self.db.flush()
        return sheet

    def promote_marker(self, payload: LearnMarkerPromote) -> LearnCard:
        """Marker in eine Lernkarte überführen oder einen unvollständigen Entwurf aktualisieren."""
        marker = self.get_marker_or_404(payload.note_id, payload.node_pm_id)
        front = payload.front.strip()

        # Ziel-Lernblatt bestimmen (Vorrang: sheet_id → session_id → course_id).
        session: LearnSession | None = None
        if payload.sheet_id is not None:
            sheet = self.get_sheet_or_404(payload.sheet_id)
        elif payload.session_id is not None:
            session = self.get_session_or_404(payload.session_id)
            sheet = self._find_or_create_session_sheet(session)
        elif payload.course_id is not None:
            self.get_course_or_404(payload.course_id)
            sheet = self._find_or_create_course_sheet(payload.course_id)
        else:
            raise BadRequestError("A target (sheet_id, session_id or course_id) is required")

        existing_stmt = (
            select(LearnCard)
            .where(
                LearnCard.source_note_id == marker.note_id,
                LearnCard.source_pm_id == marker.node_pm_id,
            )
            .order_by(LearnCard.created_at.desc())
        )
        if self.owner_id is not None:
            existing_stmt = existing_stmt.where(LearnCard.owner_id == self.owner_id)
        card = self.db.execute(existing_stmt).scalars().first()
        if card is None:
            card = LearnCard(
                owner_id=self.owner_id,
                sheet_id=sheet.id,
                position=self._next_card_position(sheet.id),
                source_note_id=marker.note_id,
                source_pm_id=marker.node_pm_id,
            )
            self.db.add(card)
        elif card.sheet_id != sheet.id:
            card.sheet_id = sheet.id
            card.position = self._next_card_position(sheet.id)
        card.kind = payload.kind
        card.front = front
        card.back = payload.back.strip() if payload.back and payload.back.strip() else None

        # Optionale dauerhafte Notiz↔Sitzung-Kopplung (künftige Marker automatisch zugeordnet).
        if payload.bind_note and session is not None and session.note_id != marker.note_id:
            self._unbind_note_from_other_sessions(marker.note_id, keep_session_id=session.id)
            session.note_id = marker.note_id

        self.db.commit()
        self.db.refresh(card)
        logger.info(
            "learn marker promoted note=%s pm=%s -> card=%s sheet=%s",
            marker.note_id,
            marker.node_pm_id,
            card.id,
            sheet.id,
        )
        return card
