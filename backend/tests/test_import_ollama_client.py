import unittest
from unittest.mock import Mock

from app.services.import_ollama_client import request_generation


class ImportOllamaClientTest(unittest.TestCase):
    def test_returns_trimmed_generation_response(self) -> None:
        response = Mock()
        response.json.return_value = {"response": "  {\"subject\":\"Strom\"}  "}
        result = request_generation(
            base_url="http://ollama:11434/",
            payload={"model": "test"},
            timeout_seconds=1,
            model="test",
            input_chars=10,
            http_post=Mock(return_value=response),
        )
        self.assertEqual(result, '{"subject":"Strom"}')

    def test_returns_none_when_http_request_fails(self) -> None:
        result = request_generation(
            base_url="http://ollama:11434",
            payload={"model": "test"},
            timeout_seconds=1,
            model="test",
            input_chars=10,
            http_post=Mock(side_effect=OSError("offline")),
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
