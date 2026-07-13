import json
import logging
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

logger = logging.getLogger("papermind.import_timing")


def now_perf() -> float:
    return time.perf_counter()


def elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 1)


def _json_safe(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Path)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def log_import_timing(event: str, **fields) -> None:
    payload = {
        "event": str(event or "").strip() or "unknown",
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    for key, value in fields.items():
        if value is None:
            continue
        payload[str(key)] = _json_safe(value)
    logger.info(
        "import_timing %s",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
