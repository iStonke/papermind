import unittest

from pydantic import ValidationError

from app.schemas.settings import AppSettingsPatch, AppSettingsRead
from app.services.settings import _merge_defaults


class SettingsValidationTest(unittest.TestCase):
    def test_theme_mode_accepts_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"ui": {"theme_mode": "dark"}})
        self.assertEqual(payload.ui.theme_mode.value, "dark")

    def test_theme_mode_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ui": {"theme_mode": "blue"}})

    def test_color_variant_accepts_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"ui": {"color_variant": "slate"}})
        self.assertEqual(payload.ui.color_variant.value, "slate")

    def test_color_variant_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ui": {"color_variant": "neon"}})

    def test_legacy_color_variant_falls_back_to_default(self) -> None:
        payload = _merge_defaults({"ui": {"color_variant": "rose"}})
        self.assertEqual(payload["ui"]["color_variant"], "slate")

    def test_sort_order_accepts_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"documents": {"sort_order": "last_opened"}})
        self.assertEqual(payload.documents.sort_order.value, "last_opened")

    def test_sort_order_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"documents": {"sort_order": "priority"}})

    def test_recent_import_window_hours_accepts_valid_value(self) -> None:
        payload = AppSettingsPatch.model_validate({"documents": {"recent_import_window_hours": 48}})
        self.assertEqual(payload.documents.recent_import_window_hours, 48)

    def test_recent_import_window_hours_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"documents": {"recent_import_window_hours": 0}})

    def test_ui_new_toggles_accept_boolean_values(self) -> None:
        payload = AppSettingsPatch.model_validate(
            {
                "ui": {
                    "showFilenameSuffix": False,
                    "drawerRememberState": True,
                    "drawerAlwaysExpanded": False,
                }
            }
        )
        self.assertIs(payload.ui.showFilenameSuffix, False)
        self.assertIs(payload.ui.drawerRememberState, True)
        self.assertIs(payload.ui.drawerAlwaysExpanded, False)

    def test_ui_new_toggle_defaults_present_in_read_model(self) -> None:
        payload = AppSettingsRead.model_validate({})
        self.assertIs(payload.ui.showFilenameSuffix, True)
        self.assertEqual(payload.ui.color_variant.value, "slate")
        self.assertIs(payload.ui.drawerRememberState, True)
        self.assertIs(payload.ui.drawerAlwaysExpanded, False)
        self.assertEqual(payload.documents.recent_import_window_hours, 24)

    def test_llm_system_prompt_rejects_too_short(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"llm": {"system_prompt": "zu kurz"}})

    def test_llm_defaults_are_present(self) -> None:
        payload = AppSettingsRead.model_validate({})
        self.assertGreaterEqual(len(payload.llm.system_prompt), 50)
        self.assertGreaterEqual(len(payload.llm.answer_prompt_template), 50)
        self.assertGreaterEqual(len(payload.llm.summary_prompt_template), 50)
        self.assertGreaterEqual(len(payload.llm.numeric_prompt_template), 50)
        self.assertEqual(payload.llm.temperature, 0.15)

    def test_rag_context_limits_accept_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"rag": {"max_context_chars": 16000}})
        self.assertEqual(payload.rag.max_context_chars, 16000)

    def test_rag_overlap_rejects_greater_or_equal_chunk_size(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsRead.model_validate({"rag": {"chunk_chars": 2000, "chunk_overlap_chars": 2000}})

    def test_ocr_engine_accepts_supported_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"ocr": {"engine": "easyocr"}})
        self.assertEqual(payload.ocr.engine.value, "easyocr")

    def test_ocr_engine_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ocr": {"engine": "legacyocr"}})


if __name__ == "__main__":
    unittest.main()
