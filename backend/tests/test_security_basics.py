import unittest

from fastapi import HTTPException

from app.core.config import Settings
from app.core.deps import _allows_file_query_token
from app.core.logging import redact_query_tokens
from app.core.security import enforce_rate_limit


class SecurityBasicsTest(unittest.TestCase):
    def test_file_query_tokens_are_limited_to_native_get_resources(self) -> None:
        document_id = "123e4567-e89b-12d3-a456-426614174000"
        self.assertTrue(_allows_file_query_token("GET", f"/api/documents/{document_id}/file"))
        self.assertTrue(_allows_file_query_token("GET", f"/api/documents/{document_id}/thumbnail"))
        self.assertTrue(_allows_file_query_token("GET", "/api/auth/me/avatar"))
        self.assertFalse(_allows_file_query_token("POST", f"/api/documents/{document_id}/file"))
        self.assertFalse(_allows_file_query_token("GET", f"/api/documents/{document_id}"))
        self.assertFalse(_allows_file_query_token("GET", "/api/settings"))

    def test_cors_origins_default_to_closed(self) -> None:
        settings = Settings(cors_allow_origins="")
        self.assertEqual(settings.cors_origins, [])

    def test_cors_origins_allow_explicit_wildcard_only(self) -> None:
        settings = Settings(cors_allow_origins="*")
        self.assertEqual(settings.cors_origins, ["*"])

    def test_cors_origins_parse_explicit_list(self) -> None:
        settings = Settings(cors_allow_origins="http://localhost:5179, http://127.0.0.1:5179")
        self.assertEqual(settings.cors_origins, ["http://localhost:5179", "http://127.0.0.1:5179"])

    def test_rate_limit_rejects_after_limit_inside_window(self) -> None:
        now = 100.0
        now_factory = lambda: now
        bucket = "test_rate_limit_rejects_after_limit_inside_window"

        enforce_rate_limit(bucket, "client", limit=2, window_seconds=60, now_factory=now_factory)
        enforce_rate_limit(bucket, "client", limit=2, window_seconds=60, now_factory=now_factory)

        with self.assertRaises(HTTPException) as raised:
            enforce_rate_limit(bucket, "client", limit=2, window_seconds=60, now_factory=now_factory)

        self.assertEqual(raised.exception.status_code, 429)

    def test_rate_limit_allows_after_window_expires(self) -> None:
        current_time = [100.0]
        bucket = "test_rate_limit_allows_after_window_expires"

        enforce_rate_limit(bucket, "client", limit=1, window_seconds=60, now_factory=lambda: current_time[0])
        current_time[0] = 161.0

        enforce_rate_limit(bucket, "client", limit=1, window_seconds=60, now_factory=lambda: current_time[0])

    def test_redacts_query_tokens_from_access_log_paths(self) -> None:
        value = "/api/documents/123/file?token=secret-token&thumb_v=1"
        self.assertEqual(redact_query_tokens(value), "/api/documents/123/file?token=<redacted>&thumb_v=1")


if __name__ == "__main__":
    unittest.main()
