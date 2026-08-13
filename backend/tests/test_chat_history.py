import unittest
import uuid

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.user import User
from app.services.chat_sessions import ChatSessionService


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
            for table in ("users", "chat_sessions", "chat_messages"):
                if connection.execute(text("SELECT to_regclass(:table)"), {"table": f"public.{table}"}).scalar() is None:
                    return False
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_schema_ready(), "Chat-Schema nicht migriert oder DB nicht erreichbar.")
class ChatHistoryPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = User(
            username=f"chat-history-{uuid.uuid4().hex[:10]}",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.owner_id = self.user.id
        self.client_session_id = uuid.uuid4()
        self.service = ChatSessionService(self.db, self.owner_id)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": self.owner_id})
        self.db.commit()
        self.db.close()

    def test_history_can_be_restored_archived_and_resumed_without_deletion(self) -> None:
        self.service.ensure_session(self.client_session_id, first_question="Welche Verträge habe ich?")
        _, assistant = self.service.append_exchange(
            self.client_session_id,
            question="Welche Verträge habe ich?",
            answer="Ein Mietvertrag ist vorhanden.",
            citations=[{"doc_id": str(uuid.uuid4()), "snippet": "Mietvertrag"}],
            knowledge_trace={"used": True, "pages": [], "claims": []},
        )
        self.db.commit()

        restored = self.service.get_latest_session_history()
        self.assertEqual(restored["session_id"], self.client_session_id)
        self.assertEqual([message["role"] for message in restored["messages"]], ["user", "assistant"])
        self.assertEqual(restored["messages"][1]["id"], assistant.id)
        self.assertEqual(self.service.list_sessions()[0]["message_count"], 2)

        self.service.archive_session(self.client_session_id)
        self.assertIsNone(self.service.get_latest_session_history())
        self.assertEqual(self.service.get_session_history(self.client_session_id)["message_count"], 2)

        self.service.ensure_session(self.client_session_id, first_question="Fortsetzung")
        self.service.append_exchange(
            self.client_session_id,
            question="Und wann läuft er aus?",
            answer="Das Ende steht im Originaldokument.",
            citations=[],
            knowledge_trace={"used": False, "pages": [], "claims": []},
        )
        self.db.commit()
        self.assertEqual(self.service.get_latest_session_history()["message_count"], 4)

class ChatHistoryRouteTest(unittest.TestCase):
    def test_chat_history_routes_are_registered_before_the_dynamic_session_route(self) -> None:
        from app.routers.ai import router

        paths = [route.path for route in router.routes]
        self.assertIn("/api/ai/sessions", paths)
        self.assertIn("/api/ai/sessions/latest", paths)
        self.assertIn("/api/ai/sessions/{session_id}", paths)
        self.assertLess(paths.index("/api/ai/sessions/latest"), paths.index("/api/ai/sessions/{session_id}"))


if __name__ == "__main__":
    unittest.main()
