import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from app.models.global_setting import GlobalSetting
from app.services.ai_credentials import AICredentialService, ai_credentials_encryption_key


class AICredentialServiceTest(unittest.TestCase):
    def test_managed_key_is_created_automatically_and_remains_stable(self) -> None:
        with TemporaryDirectory() as directory:
            key_path = Path(directory) / "credentials.key"
            with (
                patch.dict(
                    "os.environ",
                    {"AI_CREDENTIALS_MANAGED_KEY_FILE": str(key_path)},
                    clear=False,
                ),
                patch("app.services.ai_credentials.backup_encryption_key", return_value=None),
            ):
                first = ai_credentials_encryption_key()
                second = ai_credentials_encryption_key()

            self.assertEqual(first, second)
            self.assertEqual(len(first), 32)
            self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)

    def test_stored_cloud_key_is_encrypted_and_only_returned_internally(self) -> None:
        row = GlobalSetting(id=1, settings_json={})
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = row
        service = AICredentialService(db)

        with (
            patch(
                "app.services.ai_credentials.ai_credentials_encryption_key",
                return_value=bytes(range(32)),
            ),
            patch.object(service, "_validate_key") as validate_key,
        ):
            status = service.set_key("openai", "sk-test-secret-value")
            stored = row.settings_json["ai_credentials"]["openai"]

            self.assertNotIn("sk-test-secret-value", json.dumps(stored))
            self.assertTrue(stored["ciphertext"].startswith("enc:v1:"))
            self.assertTrue(stored["validated"])
            self.assertEqual(service.get_key("openai"), "sk-test-secret-value")
            self.assertTrue(status.openai.configured)
            self.assertEqual(status.openai.source, "stored")
            self.assertNotIn("sk-test-secret-value", status.model_dump_json())
            validate_key.assert_called_once_with("openai", "sk-test-secret-value")

    def test_rejected_cloud_key_is_not_stored(self) -> None:
        row = GlobalSetting(id=1, settings_json={})
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = row
        service = AICredentialService(db)

        with patch.object(service, "_validate_key", side_effect=ValueError("abgelehnt")):
            with self.assertRaises(ValueError):
                service.set_key("anthropic", "sk-ant-invalid-value")

        self.assertNotIn("ai_credentials", row.settings_json)
        db.commit.assert_not_called()

    def test_provider_validation_rejects_unauthorized_key(self) -> None:
        response = MagicMock(status_code=401)
        with patch("app.services.ai_credentials.httpx.get", return_value=response) as request:
            with self.assertRaisesRegex(ValueError, "abgelehnt"):
                AICredentialService._validate_key("openai", "sk-invalid-value")

        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], "https://api.openai.com/v1/models")
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"],
            "Bearer sk-invalid-value",
        )

    def test_provider_validation_accepts_anthropic_key(self) -> None:
        response = MagicMock(status_code=200)
        with patch("app.services.ai_credentials.httpx.get", return_value=response) as request:
            AICredentialService._validate_key("anthropic", "sk-ant-valid-value")

        self.assertEqual(request.call_args.args[0], "https://api.anthropic.com/v1/models")
        self.assertEqual(request.call_args.kwargs["headers"]["x-api-key"], "sk-ant-valid-value")

    def test_legacy_unvalidated_key_does_not_enable_ai_actions(self) -> None:
        row = GlobalSetting(
            id=1,
            settings_json={"ai_credentials": {"openai": "enc:v1:legacy-value"}},
        )
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = row
        service = AICredentialService(db)

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            status = service.status()
            key = service.get_key("openai")

        self.assertFalse(status.openai.configured)
        self.assertEqual(status.openai.source, "stored")
        self.assertEqual(key, "")


if __name__ == "__main__":
    unittest.main()
