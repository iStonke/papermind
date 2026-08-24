"""Provider-neutral, streamed text generation for PaperMind notes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator, Literal

import httpx
from sqlalchemy.orm import Session

from app.schemas.notes import NoteTextGenerationRequest
from app.schemas.settings import NOTE_WRITING_SYSTEM_PROMPT_DEFAULT
from app.services.ai_credentials import AICredentialService
from app.services.settings import SettingsService


Provider = Literal["ollama", "openai", "anthropic"]

@dataclass(frozen=True)
class GenerationPlan:
    provider: Provider
    model: str
    system_prompt: str
    user_prompt: str
    api_key: str
    base_url: str
    timeout_seconds: float
    max_output_tokens: int
    temperature: float
    local_only: bool


def _ndjson(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _user_prompt(payload: NoteTextGenerationRequest, context_limit: int) -> str:
    note_context = payload.note_context[-context_limit:].strip()
    sections = [f"NUTZERANWEISUNG:\n{payload.instruction.strip()}"]
    if note_context:
        sections.append(f"TEXT VOR DEM CURSOR:\n{note_context}")
    if payload.selected_text.strip():
        sections.append(f"AUSGEWÄHLTER TEXT:\n{payload.selected_text.strip()}")
    if payload.document_context.strip():
        sections.append(f"LOKALER DOKUMENTKONTEXT:\n{payload.document_context.strip()}")
    return "\n\n".join(sections)


class NoteAIService:
    def __init__(self, db: Session, owner_id):
        self.db = db
        self.owner_id = owner_id

    def prepare(self, payload: NoteTextGenerationRequest) -> GenerationPlan:
        runtime = SettingsService(self.db, self.owner_id).get_settings()
        cfg = runtime.text_generation
        if not cfg.enabled:
            raise ValueError("Textgenerierung ist in den Einstellungen deaktiviert")

        # Harte Datenschutzgrenze: Sobald Dokumentkontext beteiligt ist, ist
        # ausschließlich das lokale Modell zulässig. Der Client kann diese
        # Einschränkung weder per Provider- noch per Modellparameter umgehen.
        local_only = bool(payload.document_context.strip())
        provider: Provider = "ollama" if local_only else cfg.provider
        model = {
            "ollama": cfg.ollama_model,
            "openai": cfg.openai_model,
            "anthropic": cfg.anthropic_model,
        }[provider]

        api_key = ""
        if provider == "ollama":
            if not runtime.ollama.enabled:
                raise ValueError("Das lokale KI-Modell ist deaktiviert")
        else:
            api_key = AICredentialService(self.db).get_key(provider)
            if not api_key:
                label = "OpenAI" if provider == "openai" else "Anthropic"
                raise ValueError(f"Für {label} ist kein API-Schlüssel konfiguriert")

        return GenerationPlan(
            provider=provider,
            model=model,
            system_prompt=str(cfg.system_prompt or NOTE_WRITING_SYSTEM_PROMPT_DEFAULT).strip(),
            user_prompt=_user_prompt(payload, int(cfg.note_context_chars)),
            api_key=api_key,
            base_url=str(runtime.ollama.base_url).rstrip("/"),
            timeout_seconds=float(runtime.ollama.timeout_seconds),
            max_output_tokens=int(cfg.max_output_tokens),
            temperature=float(cfg.temperature),
            local_only=local_only,
        )

    def stream(self, plan: GenerationPlan) -> Iterator[str]:
        yield _ndjson({
            "type": "meta",
            "provider": plan.provider,
            "model": plan.model,
            "local_only": plan.local_only,
        })
        produced = False
        try:
            for delta in self._provider_stream(plan):
                if not delta:
                    continue
                produced = True
                yield _ndjson({"type": "delta", "text": delta})
        except Exception as exc:
            yield _ndjson({"type": "error", "message": self._safe_error(exc)})
            return
        if not produced:
            yield _ndjson({"type": "error", "message": "Das Modell hat keinen Text erzeugt."})
            return
        yield _ndjson({"type": "done"})

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.TimeoutException):
            return "Das KI-Modell hat nicht rechtzeitig geantwortet."
        if isinstance(exc, httpx.HTTPStatusError):
            return f"Der KI-Anbieter hat die Anfrage abgelehnt ({exc.response.status_code})."
        return "Text konnte nicht generiert werden. Bitte Verbindung und Modell prüfen."

    def _provider_stream(self, plan: GenerationPlan) -> Iterator[str]:
        if plan.provider == "ollama":
            yield from self._ollama_stream(plan)
        elif plan.provider == "openai":
            yield from self._openai_stream(plan)
        else:
            yield from self._anthropic_stream(plan)

    @staticmethod
    def _ollama_stream(plan: GenerationPlan) -> Iterator[str]:
        payload = {
            "model": plan.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": plan.system_prompt},
                {"role": "user", "content": plan.user_prompt},
            ],
            "options": {"temperature": plan.temperature, "num_predict": plan.max_output_tokens},
        }
        with httpx.stream("POST", f"{plan.base_url}/api/chat", json=payload, timeout=plan.timeout_seconds) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                text = str((data.get("message") or {}).get("content") or "")
                if text:
                    yield text

    @staticmethod
    def _openai_stream(plan: GenerationPlan) -> Iterator[str]:
        payload = {
            "model": plan.model,
            "instructions": plan.system_prompt,
            "input": plan.user_prompt,
            "max_output_tokens": plan.max_output_tokens,
            "stream": True,
            "store": False,
        }
        headers = {"Authorization": f"Bearer {plan.api_key}", "Content-Type": "application/json"}
        with httpx.stream(
            "POST", "https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=plan.timeout_seconds
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                data = json.loads(raw)
                if data.get("type") == "response.output_text.delta":
                    yield str(data.get("delta") or "")

    @staticmethod
    def _anthropic_stream(plan: GenerationPlan) -> Iterator[str]:
        payload = {
            "model": plan.model,
            "system": plan.system_prompt,
            "messages": [{"role": "user", "content": plan.user_prompt}],
            "max_tokens": plan.max_output_tokens,
            "temperature": plan.temperature,
            "stream": True,
        }
        headers = {
            "x-api-key": plan.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        with httpx.stream(
            "POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=plan.timeout_seconds
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                data = json.loads(raw)
                delta = data.get("delta") or {}
                if data.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    yield str(delta.get("text") or "")
