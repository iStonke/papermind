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

    def test_legacy_color_variant_is_removed(self) -> None:
        payload = _merge_defaults({"ui": {"color_variant": "rose"}})
        self.assertNotIn("color_variant", payload["ui"])

    def test_sort_order_accepts_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"documents": {"sort_order": "last_opened"}})
        self.assertEqual(payload.documents.sort_order.value, "last_opened")

    def test_sort_order_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"documents": {"sort_order": "priority"}})

    def test_recent_import_window_hours_accepts_valid_value(self) -> None:
        payload = AppSettingsPatch.model_validate({"documents": {"recent_import_window_hours": 48}})
        self.assertEqual(payload.documents.recent_import_window_hours, 48)

    def test_auto_open_import_inbox_accepts_boolean_value(self) -> None:
        payload = AppSettingsPatch.model_validate({"documents": {"auto_open_import_inbox": True}})
        self.assertIs(payload.documents.auto_open_import_inbox, True)

    def test_recent_import_window_hours_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"documents": {"recent_import_window_hours": 0}})

    def test_ui_new_toggles_accept_boolean_values(self) -> None:
        payload = AppSettingsPatch.model_validate(
            {
                "ui": {
                    "showFilenameSuffix": False,
                    "previewDrawerGradientEnabled": False,
                    "autoHideDetailsDrawer": True,
                    "drawerRememberState": True,
                    "tagDrawerRememberState": False,
                    "sidebar_show_dossiers": False,
                }
            }
        )
        self.assertIs(payload.ui.showFilenameSuffix, False)
        self.assertIs(payload.ui.previewDrawerGradientEnabled, False)
        self.assertIs(payload.ui.autoHideDetailsDrawer, True)
        self.assertIs(payload.ui.drawerRememberState, True)
        self.assertIs(payload.ui.tagDrawerRememberState, False)
        self.assertIs(payload.ui.sidebar_show_dossiers, False)

    def test_ui_new_toggle_defaults_present_in_read_model(self) -> None:
        payload = AppSettingsRead.model_validate({})
        self.assertIs(payload.ui.showFilenameSuffix, True)
        self.assertIs(payload.ui.previewDrawerGradientEnabled, True)
        self.assertIs(payload.ui.autoHideDetailsDrawer, False)
        self.assertIs(payload.ui.drawerRememberState, True)
        self.assertIs(payload.ui.tagDrawerRememberState, True)
        self.assertIs(payload.ui.sidebar_show_dossiers, True)
        self.assertIs(payload.documents.auto_open_import_inbox, False)
        self.assertEqual(payload.documents.recent_import_window_hours, 24)

    def test_notes_preferences_accept_supported_values(self) -> None:
        payload = AppSettingsPatch.model_validate(
            {
                "ui": {
                    "notes_default_view": "focus",
                    "notes_sort_order": "created",
                    "notes_writing_width": "wide",
                    "notes_paragraph_spacing": "spacious",
                    "notes_font_family": "serif",
                    "notes_spellcheck_enabled": False,
                }
            }
        )
        self.assertEqual(payload.ui.notes_default_view.value, "focus")
        self.assertEqual(payload.ui.notes_sort_order.value, "created")
        self.assertEqual(payload.ui.notes_writing_width.value, "wide")
        self.assertEqual(payload.ui.notes_paragraph_spacing.value, "spacious")
        self.assertEqual(payload.ui.notes_font_family.value, "serif")
        self.assertIs(payload.ui.notes_spellcheck_enabled, False)

    def test_notes_preferences_reject_unknown_values(self) -> None:
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ui": {"notes_writing_width": "unlimited"}})
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ui": {"notes_paragraph_spacing": "huge"}})
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"ui": {"notes_font_family": "comic"}})

    def test_notes_preference_defaults_are_present(self) -> None:
        payload = AppSettingsRead.model_validate({})
        self.assertEqual(payload.ui.notes_default_view.value, "remember")
        self.assertEqual(payload.ui.notes_sort_order.value, "updated")
        self.assertEqual(payload.ui.notes_writing_width.value, "comfortable")
        self.assertEqual(payload.ui.notes_paragraph_spacing.value, "comfortable")
        self.assertEqual(payload.ui.notes_font_family.value, "sans")
        self.assertIs(payload.ui.notes_spellcheck_enabled, True)

    def test_legacy_favorite_sidebar_visibility_is_removed(self) -> None:
        payload = _merge_defaults({"ui": {"sidebar_show_favorites": False}})
        self.assertNotIn("sidebar_show_favorites", payload["ui"])

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
        self.assertEqual(payload.ocr.language, "deu+eng")
        self.assertIs(payload.ocr.use_unpaper, True)

    def test_note_text_generation_has_independent_provider_routing(self) -> None:
        defaults = AppSettingsRead.model_validate({})
        self.assertEqual(defaults.text_generation.provider, "ollama")
        self.assertEqual(defaults.ollama.chat_model, "llama3.2:3b")
        self.assertGreaterEqual(len(defaults.text_generation.system_prompt), 50)
        self.assertNotIn("ai_credentials", defaults.model_dump())

        patch = AppSettingsPatch.model_validate(
            {
                "text_generation": {
                    "provider": "openai",
                    "openai_model": "gpt-test",
                    "system_prompt": "Eigene interne Schreibanweisung mit mindestens fünfzig Zeichen Länge.",
                }
            }
        )
        self.assertEqual(patch.text_generation.provider, "openai")
        self.assertEqual(patch.text_generation.openai_model, "gpt-test")
        self.assertIn("Schreibanweisung", patch.text_generation.system_prompt)

        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"text_generation": {"provider": "cloud-auto"}})
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"text_generation": {"system_prompt": "zu kurz"}})

    def test_rag_context_limits_accept_valid_values(self) -> None:
        payload = AppSettingsPatch.model_validate({"rag": {"max_context_chars": 16000}})
        self.assertEqual(payload.rag.max_context_chars, 16000)

    def test_wiki_trust_defaults_and_limits_are_present(self) -> None:
        defaults = AppSettingsRead.model_validate({})
        self.assertIs(defaults.wiki.enabled, True)
        self.assertIs(defaults.wiki.llm_claim_extraction, True)
        self.assertIs(defaults.wiki.require_review_for_chat_capture, True)

        patch = AppSettingsPatch.model_validate({"wiki": {"page_limit": 8, "claim_limit": 40}})
        self.assertEqual(patch.wiki.page_limit, 8)
        self.assertEqual(patch.wiki.claim_limit, 40)

        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"wiki": {"claim_limit": 2}})
        with self.assertRaises(ValidationError):
            AppSettingsPatch.model_validate({"wiki": {"require_review_for_chat_capture": False}})

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
