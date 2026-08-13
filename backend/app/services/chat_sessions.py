"""Persistent, owner-scoped chat history used for follow-up retrieval."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.chat import ChatMessage, ChatSession


class ChatSessionService:
    def __init__(self, db: Session, owner_id: uuid.UUID):
        self.db = db
        self.owner_id = owner_id

    @staticmethod
    def _compact(value: str, limit: int | None = None) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if limit is not None and len(normalized) > limit:
            return f"{normalized[:limit].rstrip()}…"
        return normalized

    def ensure_session(self, client_session_id: uuid.UUID, *, first_question: str | None = None) -> ChatSession:
        session = self.db.execute(
            select(ChatSession).where(
                ChatSession.owner_id == self.owner_id,
                ChatSession.client_session_id == client_session_id,
            )
        ).scalar_one_or_none()
        if session is None:
            session = ChatSession(
                owner_id=self.owner_id,
                client_session_id=client_session_id,
                title=self._compact(first_question or "", 120) or None,
            )
            self.db.add(session)
            self.db.flush()
        elif not session.title and first_question:
            session.title = self._compact(first_question, 120) or None
        if session.archived_at is not None:
            session.archived_at = None
        return session

    def get_session(self, client_session_id: uuid.UUID) -> ChatSession:
        session = self.db.execute(
            select(ChatSession).where(
                ChatSession.owner_id == self.owner_id,
                ChatSession.client_session_id == client_session_id,
            )
        ).scalar_one_or_none()
        if session is None:
            raise NotFoundError("Chat session not found", details={"session_id": str(client_session_id)})
        return session

    def load_recent_messages(self, client_session_id: uuid.UUID, *, limit: int = 6) -> list[dict[str, Any]]:
        session = self.db.execute(
            select(ChatSession.id).where(
                ChatSession.owner_id == self.owner_id,
                ChatSession.client_session_id == client_session_id,
            )
        ).scalar_one_or_none()
        if session is None:
            return []
        rows = self.db.execute(
            select(ChatMessage.role, ChatMessage.content, ChatMessage.created_at)
            .where(ChatMessage.owner_id == self.owner_id, ChatMessage.session_id == session)
            .order_by(ChatMessage.sequence_number.desc())
            .limit(max(1, min(int(limit), 50)))
        ).all()
        return [
            {"role": role, "content": content, "created_at": created_at.timestamp()}
            for role, content, created_at in reversed(rows)
        ]

    @staticmethod
    def _session_summary(session: ChatSession, *, message_count: int) -> dict[str, Any]:
        return {
            "session_id": session.client_session_id,
            "title": session.title,
            "message_count": int(message_count or 0),
            "archived_at": session.archived_at,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def list_sessions(self, *, limit: int = 30) -> list[dict[str, Any]]:
        message_counts = (
            select(ChatMessage.session_id, func.count(ChatMessage.id).label("message_count"))
            .where(ChatMessage.owner_id == self.owner_id)
            .group_by(ChatMessage.session_id)
            .subquery()
        )
        rows = self.db.execute(
            select(ChatSession, func.coalesce(message_counts.c.message_count, 0))
            .outerjoin(message_counts, message_counts.c.session_id == ChatSession.id)
            .where(ChatSession.owner_id == self.owner_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .limit(max(1, min(int(limit), 100)))
        ).all()
        return [self._session_summary(session, message_count=message_count) for session, message_count in rows]

    def get_session_history(self, client_session_id: uuid.UUID, *, message_limit: int = 500) -> dict[str, Any]:
        session = self.get_session(client_session_id)
        message_total = int(
            self.db.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.owner_id == self.owner_id,
                    ChatMessage.session_id == session.id,
                )
            )
            or 0
        )
        rows = list(
            self.db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.owner_id == self.owner_id,
                    ChatMessage.session_id == session.id,
                )
                .order_by(ChatMessage.sequence_number.desc())
                .limit(max(1, min(int(message_limit), 1000)))
            ).scalars()
        )
        messages = [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "citations": list(message.citations or []),
                "knowledge_trace": message.knowledge_trace,
                "created_at": message.created_at,
            }
            for message in reversed(rows)
        ]
        return {**self._session_summary(session, message_count=message_total), "messages": messages}

    def get_latest_session_history(self, *, message_limit: int = 500) -> dict[str, Any] | None:
        session_id = self.db.execute(
            select(ChatSession.client_session_id)
            .where(
                ChatSession.owner_id == self.owner_id,
                ChatSession.archived_at.is_(None),
            )
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if session_id is None:
            return None
        return self.get_session_history(session_id, message_limit=message_limit)

    def archive_session(self, client_session_id: uuid.UUID) -> dict[str, Any]:
        session = self.get_session(client_session_id)
        message_count = int(
            self.db.scalar(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.owner_id == self.owner_id,
                    ChatMessage.session_id == session.id,
                )
            )
            or 0
        )
        now = datetime.now(timezone.utc)
        session.archived_at = now
        session.updated_at = now
        self.db.commit()
        return self._session_summary(session, message_count=message_count)

    def append_exchange(
        self,
        client_session_id: uuid.UUID,
        *,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        knowledge_trace: dict[str, Any] | None,
    ) -> tuple[ChatMessage, ChatMessage]:
        session = self.db.execute(
            select(ChatSession)
            .where(
                ChatSession.owner_id == self.owner_id,
                ChatSession.client_session_id == client_session_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if session is None:
            session = self.ensure_session(client_session_id, first_question=question)

        current = self.db.scalar(
            select(func.max(ChatMessage.sequence_number)).where(ChatMessage.session_id == session.id)
        )
        next_sequence = int(current or 0) + 1
        user_message = ChatMessage(
            owner_id=self.owner_id,
            session_id=session.id,
            sequence_number=next_sequence,
            role="user",
            content=self._compact(question),
            citations=[],
        )
        assistant_message = ChatMessage(
            owner_id=self.owner_id,
            session_id=session.id,
            sequence_number=next_sequence + 1,
            role="assistant",
            content=str(answer or "").strip(),
            citations=jsonable_encoder(citations),
            knowledge_trace=jsonable_encoder(knowledge_trace) if knowledge_trace else None,
        )
        self.db.add_all([user_message, assistant_message])
        session.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return user_message, assistant_message

    def get_assistant_message(self, client_session_id: uuid.UUID, message_id: uuid.UUID) -> ChatMessage:
        session = self.get_session(client_session_id)
        message = self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session.id,
                ChatMessage.owner_id == self.owner_id,
                ChatMessage.role == "assistant",
            )
        ).scalar_one_or_none()
        if message is None:
            raise NotFoundError("Chat message not found", details={"message_id": str(message_id)})
        return message
