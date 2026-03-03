import unittest

from app.core.errors import BadRequestError
from app.services.smart_folder_query import SmartFolderQueryCompiler, validate_smart_folder_query


class SmartFolderQueryValidationTest(unittest.TestCase):
    def test_valid_query_with_two_rules(self) -> None:
        raw_query = {
            "version": 1,
            "group": {
                "op": "AND",
                "rules": [
                    {"field": "title", "op": "contains", "value": "Rechnung"},
                    {"field": "ocr_status", "op": "equals", "value": "done"},
                ],
            },
        }

        normalized = validate_smart_folder_query(raw_query)

        self.assertEqual(normalized["version"], 1)
        self.assertEqual(normalized["group"]["op"], "AND")
        self.assertEqual(len(normalized["group"]["rules"]), 2)

    def test_invalid_version_raises_bad_request(self) -> None:
        raw_query = {"version": 2, "group": {"op": "AND", "rules": [{"field": "title", "op": "contains", "value": "x"}]}}
        with self.assertRaises(BadRequestError):
            validate_smart_folder_query(raw_query)

    def test_invalid_operator_for_field_raises_bad_request(self) -> None:
        raw_query = {
            "version": 1,
            "group": {
                "op": "AND",
                "rules": [{"field": "ocr_status", "op": "contains", "value": "done"}],
            },
        }
        with self.assertRaises(BadRequestError):
            validate_smart_folder_query(raw_query)


class SmartFolderQueryCompilerTest(unittest.TestCase):
    def test_compile_nested_group_returns_expression(self) -> None:
        compiler = SmartFolderQueryCompiler()
        raw_query = {
            "version": 1,
            "group": {
                "op": "AND",
                "rules": [
                    {"field": "filename", "op": "ends_with", "value": ".pdf"},
                    {
                        "type": "group",
                        "group": {
                            "op": "OR",
                            "rules": [
                                {"field": "tags", "op": "contains", "value": "Steuer"},
                                {"field": "doc_date", "op": "after", "value": "2026-01-01"},
                            ],
                        },
                    },
                ],
            },
        }

        compiled = compiler.compile(raw_query)

        self.assertIsNotNone(compiled)
        self.assertIn("documents", str(compiled))


if __name__ == "__main__":
    unittest.main()
