import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.search_event import SearchEvent

logger = logging.getLogger("papermind.search_events")

# Suchbegriffe werden normalisiert und gekürzt gespeichert.
MAX_TERM_LENGTH = 120


class SearchEventService:
    def __init__(self, db: Session, owner_id):
        self.db = db
        self.owner_id = owner_id

    @staticmethod
    def normalize(term: str) -> str:
        return " ".join(str(term or "").split())[:MAX_TERM_LENGTH].strip()

    def record(self, term: str) -> None:
        normalized = self.normalize(term)
        if not normalized or self.owner_id is None:
            return
        self.db.add(SearchEvent(owner_id=self.owner_id, term=normalized))
        self.db.commit()

    def top_terms(self, limit: int = 5) -> list[tuple[str, int]]:
        # Gruppierung case-insensitiv, damit "Rechnung" und "rechnung" zusammenfallen.
        key = func.lower(SearchEvent.term)
        stmt = (
            select(func.min(SearchEvent.term).label("term"), func.count().label("count"))
            .group_by(key)
            .order_by(func.count().desc(), func.min(SearchEvent.term).asc())
            .limit(limit)
        )
        if self.owner_id is not None:
            stmt = stmt.where(SearchEvent.owner_id == self.owner_id)
        return [(row.term, int(row.count or 0)) for row in self.db.execute(stmt).all()]
