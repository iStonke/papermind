"""Provider-neutral, streamed text generation for PaperMind notes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from dataclasses import replace
from typing import Iterator, Literal

import httpx
from sqlalchemy.orm import Session

from app.schemas.notes import NoteTextGenerationRequest
from app.schemas.settings import NOTE_WRITING_SYSTEM_PROMPT_DEFAULT
from app.services.ai_credentials import AICredentialService
from app.services.settings import SettingsService


Provider = Literal["ollama", "openai", "anthropic"]
logger = logging.getLogger("papermind.note_ai")


class NoteAIProviderError(RuntimeError):
    """Provider failure that is safe to surface to the signed-in user."""


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
    fallback_model: str = ""


def _ndjson(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _user_prompt(payload: NoteTextGenerationRequest, context_limit: int) -> str:
    note_context = payload.note_context[-context_limit:].strip()
    sections = [f"NUTZERANWEISUNG:\n{payload.instruction.strip()}"]
    length_instruction = " ".join(payload.length_instruction.split())
    if length_instruction:
        sections.append(
            "VERBINDLICHE LÄNGENVORGABE:\n"
            f"{length_instruction}\n"
            "Halte diese Länge ein und gib keinen zusätzlichen Vor- oder Nachsatz aus."
        )
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
            fallback_model=(
                str(cfg.ollama_model).strip()
                if provider != "ollama" and runtime.ollama.enabled
                else ""
            ),
        )

    def stream(self, plan: GenerationPlan) -> Iterator[str]:
        yield _ndjson(self._meta_event(plan))
        produced = False
        failure: Exception | None = None
        fallback_succeeded = False
        try:
            for delta in self._provider_stream_with_retry(plan):
                if not delta:
                    continue
                produced = True
                yield _ndjson({"type": "delta", "text": delta})
        except Exception as exc:
            failure = exc
            self._log_failure(plan, exc, fallback=False)

        # Ein ausgefallener oder leer antwortender Cloud-Anbieter darf die
        # Schreibassistenz nicht komplett blockieren, wenn das lokale Modell
        # verfügbar ist. Der Fallback startet nur vor dem ersten Delta, damit
        # niemals zwei Antworten ineinander geraten.
        if not produced and plan.provider != "ollama" and plan.fallback_model:
            fallback = replace(
                plan,
                provider="ollama",
                model=plan.fallback_model,
                api_key="",
                fallback_model="",
            )
            yield _ndjson(self._meta_event(fallback, fallback_from=plan.provider))
            try:
                for delta in self._provider_stream_with_retry(fallback):
                    if not delta:
                        continue
                    produced = True
                    fallback_succeeded = True
                    yield _ndjson({"type": "delta", "text": delta})
            except Exception as fallback_exc:
                self._log_failure(fallback, fallback_exc, fallback=True)
                yield _ndjson({"type": "error", "message": self._safe_error(fallback_exc)})
                return

        if failure is not None and not fallback_succeeded:
            yield _ndjson({"type": "error", "message": self._safe_error(failure)})
            return
        if not produced:
            yield _ndjson({"type": "error", "message": "Das Modell hat keinen Text erzeugt."})
            return
        yield _ndjson({"type": "done"})

    @staticmethod
    def _meta_event(plan: GenerationPlan, *, fallback_from: Provider | None = None) -> dict:
        event = {
            "type": "meta",
            "provider": plan.provider,
            "model": plan.model,
            "local_only": plan.local_only,
        }
        if fallback_from:
            event["fallback_from"] = fallback_from
        return event

    @staticmethod
    def _log_failure(plan: GenerationPlan, exc: Exception, *, fallback: bool) -> None:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning(
            "note_ai_provider_failed provider=%s model=%s status=%s fallback=%s error_type=%s",
            plan.provider,
            plan.model,
            status,
            fallback,
            type(exc).__name__,
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, NoteAIProviderError):
            return str(exc)
        if isinstance(exc, httpx.TimeoutException):
            return "Das KI-Modell hat nicht rechtzeitig geantwortet."
        if isinstance(exc, httpx.RequestError):
            return "Der KI-Anbieter ist derzeit nicht erreichbar."
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 401:
                return "Der konfigurierte API-Schlüssel wurde vom KI-Anbieter abgelehnt."
            if status == 403:
                return "Der API-Zugang darf das ausgewählte KI-Modell nicht verwenden."
            if status == 404:
                return "Das ausgewählte KI-Modell ist für diesen API-Zugang nicht verfügbar."
            if status == 429:
                return "Das Anfrage- oder Guthabenlimit des KI-Anbieters ist erreicht."
            if status >= 500:
                return "Der KI-Anbieter ist vorübergehend nicht verfügbar."
            return f"Der KI-Anbieter hat die Anfrage abgelehnt ({status})."
        return "Text konnte nicht generiert werden. Bitte Verbindung und Modell prüfen."

    def _provider_stream_with_retry(self, plan: GenerationPlan) -> Iterator[str]:
        """Retry one transient failure, but never after visible output."""

        for attempt in range(2):
            produced = False
            try:
                for delta in self._provider_stream(plan):
                    produced = produced or bool(delta)
                    yield delta
                return
            except Exception as exc:
                retryable = (
                    isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
                    or (
                        isinstance(exc, httpx.HTTPStatusError)
                        and (exc.response.status_code in {408, 429} or exc.response.status_code >= 500)
                    )
                )
                # Bei einem konfigurierten lokalen Fallback ist dieser der
                # schnellere zweite Versuch; den ausgefallenen Cloud-Aufruf
                # nicht vorher noch einmal mit demselben Payload wiederholen.
                if plan.provider != "ollama" and plan.fallback_model:
                    retryable = False
                if attempt == 0 and not produced and retryable:
                    continue
                raise

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
                if data.get("error"):
                    raise NoteAIProviderError("Das lokale KI-Modell hat die Anfrage abgelehnt.")
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
            # Notiztext ist eine direkte Schreibaufgabe. Ohne diese Angabe kann
            # ein Reasoning-Modell das knappe Ausgabelimit vollständig für
            # interne Denktokens verbrauchen und ohne sichtbaren Text enden.
            "reasoning": {"effort": "none"},
            "stream": True,
            "store": False,
        }
        headers = {"Authorization": f"Bearer {plan.api_key}", "Content-Type": "application/json"}
        with httpx.stream(
            "POST",
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
            timeout=min(plan.timeout_seconds, 45.0),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                data = json.loads(raw)
                event_type = data.get("type")
                if event_type == "response.output_text.delta":
                    yield str(data.get("delta") or "")
                elif event_type in {"error", "response.failed"}:
                    error = data.get("error") or (data.get("response") or {}).get("error") or {}
                    code = str(error.get("code") or "")
                    if code in {"rate_limit_exceeded", "insufficient_quota"}:
                        raise NoteAIProviderError("Das Anfrage- oder Guthabenlimit von OpenAI ist erreicht.")
                    raise NoteAIProviderError("OpenAI konnte keinen Text erzeugen.")
                elif event_type == "response.incomplete":
                    details = (data.get("response") or {}).get("incomplete_details") or {}
                    if details.get("reason") == "max_output_tokens":
                        raise NoteAIProviderError("Das Ausgabelimit war für die Antwort zu klein.")
                    raise NoteAIProviderError("OpenAI hat die Antwort vorzeitig beendet.")

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
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=min(plan.timeout_seconds, 45.0),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("type") == "error":
                    raise NoteAIProviderError("Anthropic konnte keinen Text erzeugen.")
                delta = data.get("delta") or {}
                if data.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    yield str(delta.get("text") or "")
