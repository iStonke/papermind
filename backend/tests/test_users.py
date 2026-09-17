import io
import unittest
import uuid
from unittest.mock import MagicMock, patch

from PIL import Image

from app.core.auth import hash_password
from app.core.errors import BadRequestError, ConflictError
from app.models.user import User
from app.schemas.auth import ProfileUpdateRequest
from app.schemas.users import UserCreateRequest
from app.services.users import (
    AVATAR_SIZE,
    UserService,
    _normalize_email,
    _normalize_optional,
    process_avatar_image,
)


def _png_bytes(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


class NormalizationTest(unittest.TestCase):
    def test_normalize_optional_trims_and_empties_to_none(self) -> None:
        self.assertIsNone(_normalize_optional(None))
        self.assertIsNone(_normalize_optional("   "))
        self.assertEqual(_normalize_optional("  Max Mustermann "), "Max Mustermann")

    def test_normalize_email_valid(self) -> None:
        self.assertEqual(_normalize_email("  user@example.com "), "user@example.com")

    def test_normalize_email_empty_is_none(self) -> None:
        self.assertIsNone(_normalize_email(None))
        self.assertIsNone(_normalize_email("  "))

    def test_normalize_email_invalid_raises(self) -> None:
        for bad in ("notanemail", "missing@domain", "@nolocal.com"):
            with self.assertRaises(BadRequestError):
                _normalize_email(bad)


class CreateUserTest(unittest.TestCase):
    def _service(self) -> UserService:
        return UserService(MagicMock())

    def test_create_sets_normalized_profile_fields(self) -> None:
        service = self._service()
        service._email_in_use = lambda email, **kw: False
        user = service.create_user(
            UserCreateRequest(
                username="  alice ",
                password="supersecret",
                display_name="  Alice A. ",
                email="ALICE@example.com",
                is_admin=False,
            )
        )
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.display_name, "Alice A.")
        self.assertEqual(user.email, "ALICE@example.com")

    def test_create_rejects_duplicate_email(self) -> None:
        service = self._service()
        service._email_in_use = lambda email, **kw: True
        with self.assertRaises(ConflictError):
            service.create_user(
                UserCreateRequest(username="bob", password="supersecret", email="dup@example.com")
            )

    def test_create_rejects_invalid_email(self) -> None:
        service = self._service()
        service._email_in_use = lambda email, **kw: False
        with self.assertRaises(BadRequestError):
            service.create_user(
                UserCreateRequest(username="bob", password="supersecret", email="invalid")
            )


class UpdateProfileTest(unittest.TestCase):
    def _user(self) -> User:
        return User(username="carol", password_hash="x", display_name="Carol", email="carol@example.com")

    def test_clears_display_name_with_empty_string(self) -> None:
        service = UserService(MagicMock())
        service._email_in_use = lambda email, **kw: False
        user = self._user()
        service.update_profile(user, ProfileUpdateRequest(display_name=""))
        self.assertIsNone(user.display_name)

    def test_updates_email(self) -> None:
        service = UserService(MagicMock())
        service._email_in_use = lambda email, **kw: False
        user = self._user()
        service.update_profile(user, ProfileUpdateRequest(email="new@example.com"))
        self.assertEqual(user.email, "new@example.com")

    def test_rejects_duplicate_email(self) -> None:
        service = UserService(MagicMock())
        service._email_in_use = lambda email, **kw: True
        user = self._user()
        with self.assertRaises(ConflictError):
            service.update_profile(user, ProfileUpdateRequest(email="taken@example.com"))

    def test_updates_and_normalizes_username(self) -> None:
        service = UserService(MagicMock())
        service._email_in_use = lambda email, **kw: False
        user = self._user()
        service.update_profile(user, ProfileUpdateRequest(username="  new  name "))
        self.assertEqual(user.username, "new name")

    def test_duplicate_username_raises_conflict(self) -> None:
        from sqlalchemy.exc import IntegrityError

        db = MagicMock()
        db.commit.side_effect = IntegrityError("stmt", {}, Exception("unique"))
        service = UserService(db)
        user = self._user()
        with patch("app.services.users.is_unique_violation", return_value=True):
            with self.assertRaises(ConflictError):
                service.update_profile(user, ProfileUpdateRequest(username="taken"))
        db.rollback.assert_called_once()


class RevokeOtherSessionsTest(unittest.TestCase):
    def test_revokes_all_but_the_kept_session(self) -> None:
        from app.services.auth_sessions import AuthSessionService

        keep_id = uuid.uuid4()
        keep = MagicMock(id=keep_id, revoked_at=None)
        other_a = MagicMock(id=uuid.uuid4(), revoked_at=None)
        other_b = MagicMock(id=uuid.uuid4(), revoked_at=None)
        service = AuthSessionService(MagicMock())
        with patch.object(service, "list_active", return_value=[keep, other_a, other_b]):
            revoked = service.revoke_others(MagicMock(), keep_id)
        self.assertEqual(revoked, 2)
        self.assertIsNone(keep.revoked_at)
        self.assertIsNotNone(other_a.revoked_at)
        self.assertIsNotNone(other_b.revoked_at)


class DeleteSelfTest(unittest.TestCase):
    def _user(self, *, is_admin: bool) -> User:
        return User(username="dave", password_hash="x", is_admin=is_admin, is_active=True)

    def test_admin_cannot_delete_self(self) -> None:
        from app.core.errors import ForbiddenError

        service = UserService(MagicMock())
        with self.assertRaises(ForbiddenError):
            service.delete_self(self._user(is_admin=True), "pw")

    def test_wrong_password_rejected(self) -> None:
        service = UserService(MagicMock())
        with patch("app.services.users.verify_password", return_value=False):
            with self.assertRaises(BadRequestError):
                service.delete_self(self._user(is_admin=False), "wrong")

    def test_valid_password_purges_user(self) -> None:
        service = UserService(MagicMock())
        service._purge_user = MagicMock()
        user = self._user(is_admin=False)
        with patch("app.services.users.verify_password", return_value=True):
            service.delete_self(user, "correct")
        service._purge_user.assert_called_once_with(user)


class AuthenticateLastLoginTest(unittest.TestCase):
    def test_successful_login_sets_last_login(self) -> None:
        service = UserService(MagicMock())
        user = User(username="dave", password_hash=hash_password("correct-password"), is_active=True)
        service.get_by_username = lambda username: user

        result = service.authenticate("dave", "correct-password")
        self.assertIs(result, user)
        self.assertIsNotNone(user.last_login_at)

    def test_wrong_password_returns_none_without_last_login(self) -> None:
        service = UserService(MagicMock())
        user = User(username="dave", password_hash=hash_password("correct-password"), is_active=True)
        service.get_by_username = lambda username: user

        result = service.authenticate("dave", "wrong-password")
        self.assertIsNone(result)
        self.assertIsNone(user.last_login_at)


class SessionRevocationTest(unittest.TestCase):
    def test_revoke_sessions_increments_version(self) -> None:
        db = MagicMock()
        service = UserService(db)
        user = User(username="erin", password_hash="x", session_version=4)

        service.revoke_sessions(user)

        self.assertEqual(user.session_version, 5)
        db.commit.assert_called_once()


class ProcessAvatarImageTest(unittest.TestCase):
    def test_valid_image_yields_square_webp(self) -> None:
        out = process_avatar_image(_png_bytes(640, 400))
        self.assertTrue(out)
        with Image.open(io.BytesIO(out)) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (AVATAR_SIZE, AVATAR_SIZE))

    def test_non_image_raises_bad_request(self) -> None:
        with self.assertRaises(BadRequestError):
            process_avatar_image(b"this is definitely not an image")


if __name__ == "__main__":
    unittest.main()
