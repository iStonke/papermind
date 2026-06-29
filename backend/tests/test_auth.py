import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import Response
from pydantic import ValidationError
from starlette.requests import Request

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.user import User
from app.routers import auth as auth_router
from app.schemas.auth import RegisterRequest


class PasswordHashingTest(unittest.TestCase):
    def test_hash_and_verify_roundtrip(self) -> None:
        encoded = hash_password("correct horse battery staple")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertTrue(verify_password("correct horse battery staple", encoded))

    def test_wrong_password_fails(self) -> None:
        encoded = hash_password("s3cret-pw")
        self.assertFalse(verify_password("s3cret-pwX", encoded))

    def test_salts_are_unique(self) -> None:
        a = hash_password("same-password")
        b = hash_password("same-password")
        self.assertNotEqual(a, b)
        self.assertTrue(verify_password("same-password", a))
        self.assertTrue(verify_password("same-password", b))

    def test_empty_inputs_are_safe(self) -> None:
        self.assertFalse(verify_password("", "scrypt$1$2$3$x$y"))
        self.assertFalse(verify_password("pw", ""))
        self.assertFalse(verify_password("pw", "not-a-valid-hash"))

    def test_empty_password_rejected_on_hash(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("")


class AccessTokenTest(unittest.TestCase):
    SECRET = "unit-test-secret-key"

    def test_create_and_decode_roundtrip(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(
            user_id,
            self.SECRET,
            ttl_seconds=3600,
            session_version=3,
            now=1_000_000,
        )
        payload = decode_access_token(token, self.SECRET, now=1_000_100)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], str(user_id))
        self.assertEqual(payload["exp"], 1_003_600)
        self.assertEqual(payload["sv"], 3)

    def test_expired_token_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), self.SECRET, ttl_seconds=60, now=1_000_000)
        self.assertIsNone(decode_access_token(token, self.SECRET, now=1_000_061))

    def test_wrong_secret_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), self.SECRET, ttl_seconds=3600, now=1_000_000)
        self.assertIsNone(decode_access_token(token, "other-secret", now=1_000_100))

    def test_tampered_payload_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), self.SECRET, ttl_seconds=3600, now=1_000_000)
        payload_b64, signature = token.split(".", 1)
        tampered = payload_b64[:-2] + ("AA" if not payload_b64.endswith("AA") else "BB")
        self.assertIsNone(decode_access_token(f"{tampered}.{signature}", self.SECRET, now=1_000_100))

    def test_garbage_token_rejected(self) -> None:
        self.assertIsNone(decode_access_token("not-a-token", self.SECRET))
        self.assertIsNone(decode_access_token("", self.SECRET))

    def test_empty_secret_rejected_on_create(self) -> None:
        with self.assertRaises(ValueError):
            create_access_token(uuid.uuid4(), "", ttl_seconds=3600)

    def test_scope_defaults_to_session(self) -> None:
        token = create_access_token(uuid.uuid4(), self.SECRET, ttl_seconds=3600, now=1_000_000)
        payload = decode_access_token(token, self.SECRET, now=1_000_100)
        self.assertEqual(payload["scope"], "session")

    def test_file_scope_is_embedded(self) -> None:
        token = create_access_token(uuid.uuid4(), self.SECRET, ttl_seconds=300, scope="file", now=1_000_000)
        payload = decode_access_token(token, self.SECRET, now=1_000_100)
        self.assertEqual(payload["scope"], "file")

    def test_refresh_scope_and_session_version_are_embedded(self) -> None:
        token = create_access_token(
            uuid.uuid4(),
            self.SECRET,
            ttl_seconds=3600,
            scope="refresh",
            session_version=7,
            now=1_000_000,
        )
        payload = decode_access_token(token, self.SECRET, now=1_000_100)
        self.assertEqual(payload["scope"], "refresh")
        self.assertEqual(payload["sv"], 7)


class RegistrationEndpointTest(unittest.TestCase):
    def _request(self) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/auth/register",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

    def test_register_creates_non_admin_user_and_starts_session(self) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        user = User(
            id=user_id,
            username="new-user",
            password_hash="x",
            display_name="New User",
            email="new@example.com",
            is_admin=False,
            is_active=True,
            session_version=0,
            created_at=datetime.now(timezone.utc),
        )
        session = AuthSession(id=session_id, user_id=user_id, token_hash="x", session_version=0)

        with (
            patch.object(auth_router, "enforce_persistent_rate_limit") as rate_limit,
            patch.object(auth_router.UserService, "create_user", return_value=user) as create_user,
            patch.object(auth_router.AuthSessionService, "create", return_value=(session, "refresh-token")),
        ):
            response = Response()
            result = auth_router.register(
                RegisterRequest(
                    username="new-user",
                    password="supersecret",
                    display_name="New User",
                    email="new@example.com",
                ),
                self._request(),
                response,
                MagicMock(),
            )

        rate_limit.assert_called_once()
        created_payload = create_user.call_args.args[0]
        self.assertFalse(created_payload.is_admin)
        self.assertEqual(result.user.username, "new-user")
        self.assertEqual(result.user.email, "new@example.com")
        self.assertIn("pm_refresh=refresh-token", response.headers["set-cookie"])

    def test_register_request_rejects_admin_field(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(
                username="new-user",
                password="supersecret",
                is_admin=True,
            )


if __name__ == "__main__":
    unittest.main()
