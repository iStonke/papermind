from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import and_, asc, desc, func, not_, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import BadRequestError
from app.models.document import Document
from app.models.document_tag import document_tags
from app.models.tag import Tag
from app.schemas.smart_folders import SmartFolderSort

ALLOWED_FIELDS = {
    "title",
    "filename",
    "tags",
    "ocr_text",
    "note",
    "doc_date",
    "created_at",
    "updated_at",
    "ocr_status",
}

ALLOWED_OPERATORS = {
    "contains",
    "equals",
    "starts_with",
    "ends_with",
    "not_contains",
    "in",
    "not_in",
    "is_empty",
    "is_not_empty",
    "gt",
    "gte",
    "lt",
    "lte",
    "before",
    "after",
    "between",
}

NO_VALUE_OPERATORS = {"is_empty", "is_not_empty"}
LIST_VALUE_OPERATORS = {"in", "not_in"}
RANGE_VALUE_OPERATORS = {"between"}

TEXT_FIELDS = {"title", "filename", "ocr_text", "note"}
TEMPORAL_DATE_FIELDS = {"doc_date"}
TEMPORAL_DATETIME_FIELDS = {"created_at", "updated_at"}
ENUM_FIELDS = {"ocr_status"}
TAG_FIELDS = {"tags"}

OCR_STATUSES = {"not_started", "queued", "running", "done", "failed"}
GROUP_OPS = {"AND", "OR"}

FIELD_ALLOWED_OPS: dict[str, set[str]] = {
    "title": {
        "contains",
        "equals",
        "starts_with",
        "ends_with",
        "not_contains",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
    },
    "filename": {
        "contains",
        "equals",
        "starts_with",
        "ends_with",
        "not_contains",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
    },
    "ocr_text": {
        "contains",
        "equals",
        "starts_with",
        "ends_with",
        "not_contains",
        "is_empty",
        "is_not_empty",
    },
    "note": {
        "contains",
        "equals",
        "starts_with",
        "ends_with",
        "not_contains",
        "is_empty",
        "is_not_empty",
    },
    "tags": {
        "contains",
        "equals",
        "not_contains",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
    },
    "doc_date": {
        "equals",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
        "gt",
        "gte",
        "lt",
        "lte",
        "before",
        "after",
        "between",
    },
    "created_at": {
        "equals",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
        "gt",
        "gte",
        "lt",
        "lte",
        "before",
        "after",
        "between",
    },
    "updated_at": {
        "equals",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
        "gt",
        "gte",
        "lt",
        "lte",
        "before",
        "after",
        "between",
    },
    "ocr_status": {
        "equals",
        "in",
        "not_in",
        "is_empty",
        "is_not_empty",
    },
}


def _raise_validation(path: str, message: str) -> None:
    raise BadRequestError(f"Invalid query_json at {path}: {message}")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_scalar_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _raise_validation(path, "value must be a string")
    normalized = " ".join(value.split()).strip()
    if not normalized:
        _raise_validation(path, "value must not be empty")
    return normalized


def _normalize_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        _raise_validation(path, "value must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        normalized_item = _normalize_scalar_string(item, f"{path}[{idx}]")
        key = normalized_item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(normalized_item)
    if not normalized:
        _raise_validation(path, "value list must not be empty")
    return normalized


def _parse_date(value: Any, path: str) -> str:
    raw = _normalize_scalar_string(value, path)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        _raise_validation(path, "date value must be ISO format YYYY-MM-DD")
    return parsed.isoformat()


def _parse_datetime(value: Any, path: str) -> str:
    raw = _normalize_scalar_string(value, path)
    try:
        if "T" not in raw and len(raw) == 10:
            parsed_date = date.fromisoformat(raw)
            parsed_dt = datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
        else:
            normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            parsed_dt = datetime.fromisoformat(normalized)
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        _raise_validation(path, "datetime value must be ISO date or datetime")
    return parsed_dt.isoformat()


def _normalize_temporal_range(field: str, value: Any, path: str) -> dict[str, str]:
    if not isinstance(value, dict):
        _raise_validation(path, "value must be an object with from/to")
    from_raw = value.get("from")
    to_raw = value.get("to")
    if from_raw is None or to_raw is None:
        _raise_validation(path, "between requires value.from and value.to")

    if field in TEMPORAL_DATE_FIELDS:
        from_value = _parse_date(from_raw, f"{path}.from")
        to_value = _parse_date(to_raw, f"{path}.to")
        if from_value > to_value:
            _raise_validation(path, "value.from must be <= value.to")
        return {"from": from_value, "to": to_value}

    from_value = _parse_datetime(from_raw, f"{path}.from")
    to_value = _parse_datetime(to_raw, f"{path}.to")
    if from_value > to_value:
        _raise_validation(path, "value.from must be <= value.to")
    return {"from": from_value, "to": to_value}


def _normalize_rule_value(field: str, op: str, raw_value: Any, path: str) -> Any:
    if op in NO_VALUE_OPERATORS:
        if raw_value not in (None, ""):
            _raise_validation(path, f"operator '{op}' does not accept a value")
        return None

    if op in RANGE_VALUE_OPERATORS:
        if field in TEMPORAL_DATE_FIELDS | TEMPORAL_DATETIME_FIELDS:
            return _normalize_temporal_range(field, raw_value, path)
        _raise_validation(path, f"operator '{op}' is not valid for field '{field}'")

    if op in LIST_VALUE_OPERATORS:
        if not isinstance(raw_value, list):
            _raise_validation(path, "value must be a list")
        if not raw_value:
            _raise_validation(path, "value list must not be empty")

        if field in TEXT_FIELDS or field in TAG_FIELDS:
            return _normalize_string_list(raw_value, path)
        if field in TEMPORAL_DATE_FIELDS:
            return [_parse_date(item, f"{path}[{idx}]") for idx, item in enumerate(raw_value)]
        if field in TEMPORAL_DATETIME_FIELDS:
            return [_parse_datetime(item, f"{path}[{idx}]") for idx, item in enumerate(raw_value)]
        if field in ENUM_FIELDS:
            values = _normalize_string_list(raw_value, path)
            for idx, value in enumerate(values):
                if value not in OCR_STATUSES:
                    _raise_validation(f"{path}[{idx}]", f"unsupported ocr_status '{value}'")
            return values
        _raise_validation(path, f"unsupported field '{field}' for list values")

    if field in TEXT_FIELDS:
        return _normalize_scalar_string(raw_value, path)

    if field in TAG_FIELDS:
        return _normalize_scalar_string(raw_value, path)

    if field in TEMPORAL_DATE_FIELDS:
        return _parse_date(raw_value, path)

    if field in TEMPORAL_DATETIME_FIELDS:
        return _parse_datetime(raw_value, path)

    if field in ENUM_FIELDS:
        value = _normalize_scalar_string(raw_value, path)
        if value not in OCR_STATUSES:
            _raise_validation(path, f"unsupported ocr_status '{value}'")
        return value

    _raise_validation(path, f"unsupported field '{field}'")
    return None  # pragma: no cover


def _normalize_node(raw_node: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw_node, dict):
        _raise_validation(path, "node must be an object")

    if raw_node.get("type") == "group":
        if "group" in raw_node:
            return {"type": "group", "group": _normalize_group(raw_node["group"], f"{path}.group")}
        return {"type": "group", "group": _normalize_group(raw_node, path)}

    if "group" in raw_node:
        return {"type": "group", "group": _normalize_group(raw_node["group"], f"{path}.group")}

    if "op" in raw_node and "rules" in raw_node and "field" not in raw_node:
        return {"type": "group", "group": _normalize_group(raw_node, path)}

    field = str(raw_node.get("field") or "").strip()
    op = str(raw_node.get("op") or "").strip()
    if not field:
        _raise_validation(path, "rule.field is required")
    if field not in ALLOWED_FIELDS:
        _raise_validation(f"{path}.field", f"unsupported field '{field}'")

    if not op:
        _raise_validation(path, "rule.op is required")
    if op not in ALLOWED_OPERATORS:
        _raise_validation(f"{path}.op", f"unsupported operator '{op}'")
    if op not in FIELD_ALLOWED_OPS[field]:
        _raise_validation(f"{path}.op", f"operator '{op}' is not allowed for field '{field}'")

    normalized_value = _normalize_rule_value(field, op, raw_node.get("value"), f"{path}.value")
    normalized_rule = {"field": field, "op": op}
    if op not in NO_VALUE_OPERATORS:
        normalized_rule["value"] = normalized_value
    return normalized_rule


def _normalize_group(raw_group: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw_group, dict):
        _raise_validation(path, "group must be an object")

    op = str(raw_group.get("op") or "").upper().strip()
    if op not in GROUP_OPS:
        _raise_validation(f"{path}.op", "must be AND or OR")

    raw_rules = raw_group.get("rules")
    if not isinstance(raw_rules, list):
        _raise_validation(f"{path}.rules", "must be a list")
    if not raw_rules:
        _raise_validation(f"{path}.rules", "must contain at least one rule")

    normalized_rules = [_normalize_node(node, f"{path}.rules[{idx}]") for idx, node in enumerate(raw_rules)]

    # Optional compatibility path for "groups" array.
    raw_groups = raw_group.get("groups")
    if raw_groups is not None:
        if not isinstance(raw_groups, list):
            _raise_validation(f"{path}.groups", "must be a list")
        for idx, group_node in enumerate(raw_groups):
            normalized_rules.append(
                {"type": "group", "group": _normalize_group(group_node, f"{path}.groups[{idx}]")}
            )

    return {"op": op, "rules": normalized_rules}


def validate_smart_folder_query(raw_query_json: Any) -> dict[str, Any]:
    if not isinstance(raw_query_json, dict):
        _raise_validation("query_json", "must be an object")

    version = raw_query_json.get("version")
    if version != 1:
        _raise_validation("query_json.version", "must be 1")

    if "group" not in raw_query_json:
        _raise_validation("query_json.group", "is required")

    normalized_group = _normalize_group(raw_query_json.get("group"), "query_json.group")
    return {"version": 1, "group": normalized_group}


class SmartFolderQueryCompiler:
    def compile(self, raw_query_json: Any) -> ColumnElement[bool]:
        query_json = validate_smart_folder_query(raw_query_json)
        return self._compile_group(query_json["group"])

    def _compile_group(self, group: dict[str, Any]) -> ColumnElement[bool]:
        clauses = [self._compile_node(node) for node in group["rules"]]
        if not clauses:
            return Document.id.is_not(None)
        if group["op"] == "AND":
            return and_(*clauses)
        return or_(*clauses)

    def _compile_node(self, node: dict[str, Any]) -> ColumnElement[bool]:
        if node.get("type") == "group":
            return self._compile_group(node["group"])
        return self._compile_rule(node)

    def _compile_rule(self, rule: dict[str, Any]) -> ColumnElement[bool]:
        field = rule["field"]
        op = rule["op"]
        value = rule.get("value")

        if field in TEXT_FIELDS:
            if field == "title":
                column = func.coalesce(Document.display_name, Document.original_filename)
            elif field == "filename":
                column = Document.original_filename
            elif field == "ocr_text":
                column = Document.text_content
            else:
                column = Document.notes
            return self._compile_string_rule(column, op, value)

        if field in TAG_FIELDS:
            return self._compile_tag_rule(op, value)

        if field in TEMPORAL_DATE_FIELDS:
            return self._compile_date_rule(Document.document_date, op, value)

        if field == "created_at":
            return self._compile_datetime_rule(Document.created_at, op, value)
        if field == "updated_at":
            return self._compile_datetime_rule(Document.updated_at, op, value)

        if field == "ocr_status":
            return self._compile_enum_rule(Document.ocr_status, op, value)

        raise BadRequestError(f"Unsupported field '{field}'")

    def _compile_string_rule(self, column, op: str, value: Any) -> ColumnElement[bool]:
        if op == "is_empty":
            return or_(column.is_(None), func.length(func.trim(column)) == 0)
        if op == "is_not_empty":
            return and_(column.is_not(None), func.length(func.trim(column)) > 0)

        if op == "contains":
            escaped = _escape_like(str(value))
            return column.ilike(f"%{escaped}%", escape="\\")
        if op == "not_contains":
            escaped = _escape_like(str(value))
            return or_(column.is_(None), not_(column.ilike(f"%{escaped}%", escape="\\")))
        if op == "starts_with":
            escaped = _escape_like(str(value))
            return column.ilike(f"{escaped}%", escape="\\")
        if op == "ends_with":
            escaped = _escape_like(str(value))
            return column.ilike(f"%{escaped}", escape="\\")
        if op == "equals":
            return func.lower(column) == str(value).lower()
        if op == "in":
            lowered_values = [str(item).lower() for item in value]
            return func.lower(column).in_(lowered_values)
        if op == "not_in":
            lowered_values = [str(item).lower() for item in value]
            return or_(column.is_(None), not_(func.lower(column).in_(lowered_values)))

        raise BadRequestError(f"Unsupported string operator '{op}'")

    def _compile_tag_rule(self, op: str, value: Any) -> ColumnElement[bool]:
        has_any_tag = (
            select(document_tags.c.document_id)
            .where(document_tags.c.document_id == Document.id)
            .exists()
        )
        if op == "is_empty":
            return not_(has_any_tag)
        if op == "is_not_empty":
            return has_any_tag

        if op == "contains":
            escaped = _escape_like(str(value))
            tag_match = (
                select(document_tags.c.document_id)
                .join(Tag, Tag.id == document_tags.c.tag_id)
                .where(
                    document_tags.c.document_id == Document.id,
                    Tag.name.ilike(f"%{escaped}%", escape="\\"),
                )
                .exists()
            )
            return tag_match

        if op == "not_contains":
            escaped = _escape_like(str(value))
            tag_match = (
                select(document_tags.c.document_id)
                .join(Tag, Tag.id == document_tags.c.tag_id)
                .where(
                    document_tags.c.document_id == Document.id,
                    Tag.name.ilike(f"%{escaped}%", escape="\\"),
                )
                .exists()
            )
            return not_(tag_match)

        if op == "equals":
            tag_match = (
                select(document_tags.c.document_id)
                .join(Tag, Tag.id == document_tags.c.tag_id)
                .where(
                    document_tags.c.document_id == Document.id,
                    func.lower(Tag.name) == str(value).lower(),
                )
                .exists()
            )
            return tag_match

        if op in {"in", "not_in"}:
            lowered_values = [str(item).lower() for item in value]
            tag_match = (
                select(document_tags.c.document_id)
                .join(Tag, Tag.id == document_tags.c.tag_id)
                .where(
                    document_tags.c.document_id == Document.id,
                    func.lower(Tag.name).in_(lowered_values),
                )
                .exists()
            )
            return tag_match if op == "in" else not_(tag_match)

        raise BadRequestError(f"Unsupported tags operator '{op}'")

    def _compile_date_rule(self, column, op: str, value: Any) -> ColumnElement[bool]:
        if op == "is_empty":
            return column.is_(None)
        if op == "is_not_empty":
            return column.is_not(None)

        if op == "equals":
            return column == date.fromisoformat(value)
        if op in {"gt", "after"}:
            return column > date.fromisoformat(value)
        if op == "gte":
            return column >= date.fromisoformat(value)
        if op in {"lt", "before"}:
            return column < date.fromisoformat(value)
        if op == "lte":
            return column <= date.fromisoformat(value)
        if op == "between":
            return column.between(date.fromisoformat(value["from"]), date.fromisoformat(value["to"]))
        if op == "in":
            return column.in_([date.fromisoformat(item) for item in value])
        if op == "not_in":
            return or_(column.is_(None), not_(column.in_([date.fromisoformat(item) for item in value])))

        raise BadRequestError(f"Unsupported date operator '{op}'")

    def _compile_datetime_rule(self, column, op: str, value: Any) -> ColumnElement[bool]:
        if op == "is_empty":
            return column.is_(None)
        if op == "is_not_empty":
            return column.is_not(None)

        def parse(raw: str) -> datetime:
            normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed

        if op == "equals":
            return column == parse(value)
        if op in {"gt", "after"}:
            return column > parse(value)
        if op == "gte":
            return column >= parse(value)
        if op in {"lt", "before"}:
            return column < parse(value)
        if op == "lte":
            return column <= parse(value)
        if op == "between":
            return column.between(parse(value["from"]), parse(value["to"]))
        if op == "in":
            return column.in_([parse(item) for item in value])
        if op == "not_in":
            return or_(column.is_(None), not_(column.in_([parse(item) for item in value])))

        raise BadRequestError(f"Unsupported datetime operator '{op}'")

    def _compile_enum_rule(self, column, op: str, value: Any) -> ColumnElement[bool]:
        if op == "is_empty":
            return column.is_(None)
        if op == "is_not_empty":
            return column.is_not(None)
        if op == "equals":
            return column == str(value)
        if op == "in":
            return column.in_([str(item) for item in value])
        if op == "not_in":
            return or_(column.is_(None), not_(column.in_([str(item) for item in value])))
        raise BadRequestError(f"Unsupported ocr_status operator '{op}'")


def build_smart_folder_sort(sort: SmartFolderSort):
    if sort == SmartFolderSort.doc_date_desc:
        return (
            desc(Document.document_date).nullslast(),
            desc(Document.created_at),
            desc(Document.id),
        )

    if sort == SmartFolderSort.title_asc:
        return (
            asc(func.lower(func.coalesce(Document.display_name, Document.original_filename))),
            desc(Document.created_at),
            desc(Document.id),
        )

    return (
        desc(Document.created_at),
        desc(Document.id),
    )
