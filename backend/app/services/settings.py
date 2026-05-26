from copy import deepcopy
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.models.global_setting import GlobalSetting
from app.schemas.settings import (
    ANSWER_PROMPT_TEMPLATE_DEFAULT,
    AppSettingsPatch,
    AppSettingsRead,
    NUMERIC_PROMPT_TEMPLATE_DEFAULT,
    SUMMARY_PROMPT_TEMPLATE_DEFAULT,
    SYSTEM_PROMPT_DEFAULT,
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "ui": {
        "theme_mode": "system",
        "color_variant": "slate",
        "showFilenameSuffix": True,
        "drawerRememberState": True,
        "drawerAlwaysExpanded": False,
    },
    "documents": {
        "auto_ocr": True,
        "auto_tagging": False,
        "sort_order": "newest",
        "recent_import_window_hours": 24,
        "trash_retention_days": 30,
    },
    "llm": {
        "system_prompt": SYSTEM_PROMPT_DEFAULT,
        "answer_prompt_template": ANSWER_PROMPT_TEMPLATE_DEFAULT,
        "summary_prompt_template": SUMMARY_PROMPT_TEMPLATE_DEFAULT,
        "numeric_prompt_template": NUMERIC_PROMPT_TEMPLATE_DEFAULT,
        "temperature": 0.15,
        "top_p": 0.9,
        "max_output_tokens": 1200,
        "embedding_model_name": "hash-384-v1",
    },
    "rag": {
        "top_k": 8,
        "min_score": 0.0,
        "max_context_chars": 12000,
        "chunk_chars": 4500,
        "chunk_overlap_chars": 600,
        "rerank_enabled": False,
        "rerank_top_k": 20,
        "rerank_final_k": 8,
    },
    "ocr": {
        "engine": "tesseract",
        "language": "deu",
        "enable_layout": True,
        "enable_table_detection": True,
        "deskew": True,
        "denoise": True,
        "dpi_target": 300,
        "postprocess_hyphenation": True,
        "remove_headers_footers": True,
    },
    "quality": {
        "enable_answer_checks": True,
        "enable_self_critique": False,
    },
    "meta": {
        "version": 1,
    },
}

COLOR_VARIANT_VALUES = {"indigo", "forest", "teal", "slate", "stone"}


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_defaults(raw_settings: dict[str, Any] | None) -> dict[str, Any]:
    base = raw_settings if isinstance(raw_settings, dict) else {}
    merged = _deep_merge_dict(DEFAULT_SETTINGS, base)
    ui_settings = merged.get("ui")
    if isinstance(ui_settings, dict) and ui_settings.get("color_variant") not in COLOR_VARIANT_VALUES:
        ui_settings["color_variant"] = DEFAULT_SETTINGS["ui"]["color_variant"]
    return merged


class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_row(self, *, for_update: bool = False) -> GlobalSetting:
        stmt = select(GlobalSetting).where(GlobalSetting.id == 1)
        if for_update:
            stmt = stmt.with_for_update()
        row = self.db.execute(stmt).scalar_one_or_none()
        if row is not None:
            return row

        row = GlobalSetting(id=1, settings_json=deepcopy(DEFAULT_SETTINGS))
        self.db.add(row)
        self.db.flush()
        return row

    @staticmethod
    def _raise_bad_request_from_validation(exc: ValidationError) -> None:
        raise BadRequestError(
            "Settings validation failed",
            details={"fields": exc.errors()},
        ) from exc

    @staticmethod
    def _normalize_version(value: Any) -> int:
        try:
            version = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, version)

    def _validate_and_prepare(
        self,
        raw_settings: dict[str, Any] | None,
        *,
        updated_at=None,
    ) -> tuple[AppSettingsRead, dict[str, Any]]:
        merged_with_defaults = _merge_defaults(raw_settings)
        try:
            validated = AppSettingsRead.model_validate(merged_with_defaults)
        except ValidationError as exc:
            self._raise_bad_request_from_validation(exc)

        normalized_known = validated.model_dump(mode="json", exclude={"meta": {"updated_at"}})
        persisted = dict(raw_settings) if isinstance(raw_settings, dict) else {}
        persisted["ui"] = normalized_known["ui"]
        persisted["documents"] = normalized_known["documents"]
        persisted["llm"] = normalized_known["llm"]
        persisted["rag"] = normalized_known["rag"]
        persisted["ocr"] = normalized_known["ocr"]
        persisted["quality"] = normalized_known["quality"]
        persisted_meta = dict(normalized_known.get("meta") or {})
        persisted_meta.pop("updated_at", None)
        persisted_meta["version"] = self._normalize_version(persisted_meta.get("version"))
        persisted["meta"] = persisted_meta

        response_payload = dict(normalized_known)
        response_payload["meta"] = {
            **persisted_meta,
            "updated_at": updated_at,
        }
        read_model = AppSettingsRead.model_validate(response_payload)
        return read_model, persisted

    def _next_version(self, current: dict[str, Any] | None) -> int:
        current_meta = current.get("meta") if isinstance(current, dict) else {}
        current_version = self._normalize_version((current_meta or {}).get("version"))
        return current_version + 1

    def get_settings(self) -> AppSettingsRead:
        row = self._get_or_create_row()
        validated, persisted = self._validate_and_prepare(row.settings_json, updated_at=row.updated_at)
        if row.settings_json != persisted:
            row.settings_json = persisted
            self.db.commit()
            self.db.refresh(row)
            validated, persisted = self._validate_and_prepare(row.settings_json, updated_at=row.updated_at)
        return validated

    def _coerce_patch_payload(self, payload: dict[str, Any] | AppSettingsPatch) -> AppSettingsPatch:
        if isinstance(payload, AppSettingsPatch):
            return payload
        try:
            return AppSettingsPatch.model_validate(payload or {})
        except ValidationError as exc:
            self._raise_bad_request_from_validation(exc)

    def update_settings(self, payload: dict[str, Any] | AppSettingsPatch) -> AppSettingsRead:
        parsed_payload = self._coerce_patch_payload(payload)
        patch_data = parsed_payload.model_dump(exclude_unset=True, mode="json")
        return self.update_settings_patch_data(patch_data)

    def update_settings_patch_data(self, patch_data: dict[str, Any]) -> AppSettingsRead:
        if not patch_data:
            return self.get_settings()

        row = self._get_or_create_row(for_update=True)
        current = row.settings_json if isinstance(row.settings_json, dict) else {}
        merged = _deep_merge_dict(current, patch_data)
        next_version = self._next_version(current)
        merged_meta = merged.get("meta") if isinstance(merged.get("meta"), dict) else {}
        merged["meta"] = {
            **merged_meta,
            "version": next_version,
        }

        validated, persisted = self._validate_and_prepare(merged, updated_at=row.updated_at)
        row.settings_json = persisted
        self.db.commit()
        self.db.refresh(row)
        validated, _ = self._validate_and_prepare(row.settings_json, updated_at=row.updated_at)
        return validated

    def reset_prompts(self) -> AppSettingsRead:
        row = self._get_or_create_row(for_update=True)
        current = row.settings_json if isinstance(row.settings_json, dict) else {}
        llm_payload = dict((current.get("llm") or {})) if isinstance(current.get("llm"), dict) else {}
        llm_payload["system_prompt"] = SYSTEM_PROMPT_DEFAULT
        llm_payload["answer_prompt_template"] = ANSWER_PROMPT_TEMPLATE_DEFAULT
        llm_payload["summary_prompt_template"] = SUMMARY_PROMPT_TEMPLATE_DEFAULT
        llm_payload["numeric_prompt_template"] = NUMERIC_PROMPT_TEMPLATE_DEFAULT
        merged = _deep_merge_dict(current, {"llm": llm_payload})
        merged_meta = merged.get("meta") if isinstance(merged.get("meta"), dict) else {}
        merged["meta"] = {
            **merged_meta,
            "version": self._next_version(current),
        }
        validated, persisted = self._validate_and_prepare(merged, updated_at=row.updated_at)
        row.settings_json = persisted
        self.db.commit()
        self.db.refresh(row)
        validated, _ = self._validate_and_prepare(row.settings_json, updated_at=row.updated_at)
        return validated
