"""Schmaler, testbar injizierbarer HTTP-Adapter für die Import-Ollama-Anfrage."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.services.import_timing import elapsed_ms, log_import_timing, now_perf

logger = logging.getLogger("papermind.import_ollama_client")


def request_generation(
    *,
    base_url: str,
    payload: dict[str, object],
    timeout_seconds: float,
    model: str,
    input_chars: int,
    http_post: Callable[..., Any],
) -> str | None:
    """Führt genau eine nicht-streamende Ollama-Generation aus und misst sie."""
    started = now_perf()
    try:
        response = http_post(
            f"{base_url.rstrip('/')}/api/generate",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        raw = str(response.json().get("response") or "").strip()
    except Exception as exc:  # noqa: BLE001 - KI ist optional
        logger.warning("ollama staging call failed: %s", exc)
        log_import_timing(
            "analysis_ollama_call",
            model=model,
            success=False,
            input_chars=input_chars,
            duration_ms=elapsed_ms(started),
        )
        return None
    log_import_timing(
        "analysis_ollama_call",
        model=model,
        success=True,
        input_chars=input_chars,
        response_chars=len(raw),
        duration_ms=elapsed_ms(started),
    )
    return raw or None
