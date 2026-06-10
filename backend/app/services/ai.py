import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models.document import Document
from app.schemas.ai import AIAskRequest, AIRequestType
from app.services.embeddings import EmbeddingService
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.ai")
settings = get_settings()

_NO_CONTEXT_SENTINEL = "KEIN KONTEXT GEFUNDEN"
_NO_CONTEXT_MESSAGE = "Im Dokumentenkontext nicht enthalten."
_TIMEOUT_MESSAGE = (
    "Antwort konnte nicht erzeugt werden (Timeout). Bitte erneut versuchen oder Dokumentindex prüfen."
)
_SESSION_HISTORY_MAX = 24
_SESSION_CONTEXT_LIMIT = 6
_FOLLOWUP_MARKERS = re.compile(
    r"\b(und|dann|danach|dazu|davon|das|dort|hier|wo|wann|welche|welcher)\b",
    re.IGNORECASE,
)
_NUMERIC_KEYWORDS = (
    "wie viel",
    "betrag",
    "summe",
    "€",
    "eur",
    "preis",
    "datum",
    "anzahl",
    "pro ",
    " gesamt",
    "monate",
    "tage",
)
_NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?")
_SESSION_MESSAGES: dict[str, deque[dict[str, Any]]] = {}
_SESSION_LOCK = threading.Lock()


class AIService:
    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id
        self.embedding_service = EmbeddingService(db, owner_id)
        self.settings_service = SettingsService(db)

    @staticmethod
    def _normalize_question(value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise BadRequestError("question must not be empty")
        return normalized

    @staticmethod
    def _normalize_whitespace(text_value: str) -> str:
        return " ".join(str(text_value or "").split()).strip()

    @staticmethod
    def _estimate_tokens(text_value: str) -> int:
        normalized = str(text_value or "").strip()
        if not normalized:
            return 0
        return max(1, int(len(normalized) / 4))

    @staticmethod
    def _new_session_id() -> uuid.UUID:
        return uuid.uuid4()

    @classmethod
    def _load_session_messages(cls, session_id: uuid.UUID, limit: int = _SESSION_CONTEXT_LIMIT) -> list[dict[str, Any]]:
        key = str(session_id)
        with _SESSION_LOCK:
            items = list(_SESSION_MESSAGES.get(key, deque()))
        if limit <= 0:
            return items
        return items[-limit:]

    @classmethod
    def _append_session_message(cls, session_id: uuid.UUID, role: str, content: str) -> None:
        normalized = cls._normalize_whitespace(content)
        if not normalized:
            return
        key = str(session_id)
        item = {
            "role": role,
            "content": normalized,
            "created_at": time.time(),
        }
        with _SESSION_LOCK:
            bucket = _SESSION_MESSAGES.get(key)
            if bucket is None:
                bucket = deque(maxlen=_SESSION_HISTORY_MAX)
                _SESSION_MESSAGES[key] = bucket
            bucket.append(item)

    @classmethod
    def _rewrite_query(cls, question: str, session_messages: list[dict[str, Any]]) -> str:
        normalized_question = cls._normalize_whitespace(question)
        if not normalized_question:
            return ""
        if not session_messages:
            return normalized_question
        if len(normalized_question) > 28 and not _FOLLOWUP_MARKERS.search(normalized_question):
            return normalized_question

        last_user = next(
            (item.get("content", "") for item in reversed(session_messages) if item.get("role") == "user"),
            "",
        )
        if not last_user:
            return normalized_question
        if cls._normalize_whitespace(last_user).lower() == normalized_question.lower():
            return normalized_question
        return cls._normalize_whitespace(f"{last_user}. Anschlussfrage: {normalized_question}")

    @classmethod
    def _detect_mode(cls, question: str, request_type: AIRequestType) -> str:
        if request_type == AIRequestType.summary:
            return "summary"
        normalized = cls._normalize_whitespace(question).lower()
        if any(keyword in normalized for keyword in _NUMERIC_KEYWORDS):
            return "numeric"
        return "answer"

    @staticmethod
    def _extract_doc_titles(chunks: list[dict[str, Any]]) -> str:
        titles = []
        seen = set()
        for chunk in chunks:
            title = str(chunk.get("document_title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(title)
            if len(titles) >= 8:
                break
        return ", ".join(titles)

    @staticmethod
    def _render_context(chunks: list[dict[str, Any]]) -> tuple[str, int]:
        if not chunks:
            return _NO_CONTEXT_SENTINEL, len(_NO_CONTEXT_SENTINEL)

        lines: list[str] = []
        char_count = 0
        for index, chunk in enumerate(chunks, start=1):
            page_from = chunk.get("page_from")
            page_to = chunk.get("page_to")
            page_label = "-"
            if isinstance(page_from, int) and page_from > 0 and isinstance(page_to, int) and page_to > 0:
                page_label = f"{page_from}-{page_to}" if page_from != page_to else str(page_from)
            elif isinstance(page_from, int) and page_from > 0:
                page_label = str(page_from)
            elif isinstance(page_to, int) and page_to > 0:
                page_label = str(page_to)

            chunk_id = chunk.get("chunk_id")
            chunk_label = str(chunk_id) if chunk_id else "n/a"
            title = str(chunk.get("document_title") or "Dokument").strip() or "Dokument"
            text_value = str(chunk.get("text") or "").strip()
            lines.extend(
                [
                    f"[Chunk {index} | Doc: {title} | Seite: {page_label} | Chunk-ID: {chunk_label}]",
                    text_value,
                    "---",
                ]
            )
            char_count += len(text_value)

        return "\n".join(lines).strip(), char_count

    @staticmethod
    def _apply_template(template: str, *, context: str, question: str, doc_titles: str) -> str:
        prompt = str(template or "")
        prompt = prompt.replace("{{context}}", context)
        prompt = prompt.replace("{{question}}", question)
        prompt = prompt.replace("{{doc_titles}}", doc_titles)
        prompt = prompt.replace("{{today}}", date.today().isoformat())
        return prompt

    def _load_document_titles(self, doc_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not doc_ids:
            return {}

        title_stmt = select(Document.id, Document.display_name, Document.original_filename).where(
            Document.id.in_(doc_ids)
        )
        if self.owner_id is not None:
            title_stmt = title_stmt.where(Document.owner_id == self.owner_id)
        rows = self.db.execute(title_stmt).all()
        titles: dict[uuid.UUID, str] = {}
        for doc_id, display_name, original_filename in rows:
            title = (display_name or original_filename or "Dokument").strip() or "Dokument"
            titles[doc_id] = title
        return titles

    @staticmethod
    def _build_mode_fallback(mode: str, *, context_missing_hint: str | None = None, timeout: bool = False) -> str:
        if timeout:
            return _TIMEOUT_MESSAGE

        missing_hint = context_missing_hint or "Benötigte Information fehlt im Dokumentenkontext."
        if mode == "summary":
            return (
                "A) Extraktion:\n"
                "- Im Dokumentenkontext nicht enthalten. [Quelle] \"Keine passenden Chunks gefunden\"\n"
                "B) Zusammenfassung:\n"
                "Im Dokumentenkontext nicht enthalten. "
                f"{missing_hint}"
            )
        if mode == "numeric":
            return (
                "1) Gefundene Werte:\n"
                "- Im Dokumentenkontext nicht enthalten.\n"
                "2) Interpretation / Ergebnis:\n"
                "Im Dokumentenkontext nicht enthalten.\n"
                "3) Plausibilitätscheck:\n"
                f"- {missing_hint}"
            )
        return (
            "1) Kurzantwort (1–3 Sätze)\n"
            "Im Dokumentenkontext nicht enthalten.\n"
            "2) Details (Bulletpoints)\n"
            "- Keine passenden Textstellen gefunden.\n"
            "3) Belege (Bulletpoints, je Beleg: [Quelle] \"Ausschnitt\")\n"
            "- Keine Belege verfügbar.\n"
            "4) Unsicherheit / fehlt im Kontext\n"
            f"- {missing_hint}"
        )

    @staticmethod
    def _snippet(text_value: str, limit: int = 180) -> str:
        compact = " ".join(str(text_value or "").split()).strip()
        if not compact:
            return ""
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit].rstrip()}..."

    def _aggregate_citations(
        self,
        chunks: list[dict[str, Any]],
        title_map: dict[uuid.UUID, str],
        max_docs: int = 4,
    ) -> list[dict[str, Any]]:
        grouped: dict[uuid.UUID, dict[str, Any]] = defaultdict(dict)
        for chunk in chunks:
            doc_id = chunk["doc_id"]
            score = float(chunk.get("score") or 0.0)
            entry = grouped.get(doc_id)
            if entry is None or score > float(entry.get("score") or 0.0):
                grouped[doc_id] = {"chunk": chunk, "score": score}

        citations: list[dict[str, Any]] = []
        ordered = sorted(grouped.items(), key=lambda item: float(item[1]["score"]), reverse=True)
        for doc_id, item in ordered[:max_docs]:
            chunk = item["chunk"]
            citations.append(
                {
                    "doc_id": doc_id,
                    "chunk_id": chunk.get("chunk_id"),
                    "chunk_index": chunk.get("chunk_index"),
                    "page_from": chunk.get("page_from"),
                    "page_to": chunk.get("page_to"),
                    "snippet": self._snippet(str(chunk.get("text") or ""), limit=130),
                    "document_title": title_map.get(doc_id, "Dokument"),
                }
            )
        return citations

    @staticmethod
    def _select_context_chunks(chunks: list[dict[str, Any]], max_context_chars: int) -> tuple[list[dict[str, Any]], int]:
        if not chunks:
            return [], 0
        ranked = sorted(chunks, key=lambda item: float(item.get("score") or 0.0), reverse=True)
        selected: list[dict[str, Any]] = []
        used_chars = 0
        seen_ids: set[Any] = set()

        for chunk in ranked:
            chunk_id = chunk.get("chunk_id")
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            text_value = str(chunk.get("text") or "")
            if not text_value:
                continue

            next_chars = used_chars + len(text_value)
            if selected and next_chars > max_context_chars:
                continue
            selected.append(chunk)
            used_chars = next_chars
            if used_chars >= max_context_chars:
                break

        return selected, used_chars

    @staticmethod
    def _contains_citation_markers(answer: str) -> bool:
        if re.search(r"\[[^\]]+\]\s*\"[^\"]+\"", answer):
            return True

        belege_match = re.search(
            r"(?is)3\)\s*belege(?:.*?)(?:\n4\)|\Z)",
            answer,
        )
        if not belege_match:
            return False

        belege_text = belege_match.group(0)
        if re.search(r"-\s*\[[^\]]+\]", belege_text):
            return True
        if '"' in belege_text and "-" in belege_text:
            return True
        return False

    def _analyze_quality_flags(
        self,
        answer: str,
        citations: list[dict[str, Any]],
        *,
        mode: str,
        repair_pass_used: bool,
    ) -> dict[str, bool]:
        normalized = str(answer or "").strip()
        empty_answer = not normalized
        has_numbers = bool(_NUMBER_PATTERN.search(normalized))
        has_inline_citations = self._contains_citation_markers(normalized)
        has_any_citations = has_inline_citations or bool(citations)

        numbers_without_citations = has_numbers and not has_any_citations
        missing_citations = mode in {"answer", "numeric", "summary"} and not has_any_citations and not empty_answer

        return {
            "empty_answer": empty_answer,
            "numbers_without_citations": numbers_without_citations,
            "missing_citations": missing_citations,
            "repair_pass_used": repair_pass_used,
        }

    def _call_chat_model(
        self,
        *,
        model_question: str,
        system_prompt: str,
        user_prompt: str,
        contexts: list[dict[str, Any]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        timeout_seconds: float,
        chat_model: str = "default",
    ) -> dict[str, Any]:
        payload = {
            "model": (chat_model or "default").strip() or "default",
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "max_sentences": 12,
            "temperature": temperature,
            "top_p": top_p,
            "question": model_question,
            "user_prompt": user_prompt,
            "contexts": contexts,
        }

        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/chat",
                json=payload,
                timeout=timeout_seconds,
            )
            duration_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            data = response.json()
            answer = str(data.get("answer") or "").strip()
            model_name = str(data.get("model") or "default").strip() or "default"
            return {
                "answer": answer,
                "model_name": model_name,
                "duration_ms": duration_ms,
                "timeout": False,
                "error": None,
                "prompt_tokens": self._estimate_tokens(system_prompt) + self._estimate_tokens(user_prompt),
                "completion_tokens": self._estimate_tokens(answer),
            }
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            return {
                "answer": "",
                "model_name": "timeout",
                "duration_ms": duration_ms,
                "timeout": True,
                "error": str(exc),
                "prompt_tokens": self._estimate_tokens(system_prompt) + self._estimate_tokens(user_prompt),
                "completion_tokens": 0,
            }
        except Exception as exc:  # pragma: no cover - runtime/network
            duration_ms = (time.perf_counter() - started) * 1000
            return {
                "answer": "",
                "model_name": "error",
                "duration_ms": duration_ms,
                "timeout": False,
                "error": str(exc),
                "prompt_tokens": self._estimate_tokens(system_prompt) + self._estimate_tokens(user_prompt),
                "completion_tokens": 0,
            }

    def ask(self, payload: AIAskRequest) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        started_total = time.perf_counter()

        session_id = payload.session_id or self._new_session_id()
        question = self._normalize_question(payload.question)
        runtime_settings = self.settings_service.get_settings()
        mode = self._detect_mode(question, payload.request_type)

        prior_messages = self._load_session_messages(session_id, limit=_SESSION_CONTEXT_LIMIT)
        rewritten_query = self._rewrite_query(question, prior_messages)
        retrieval_top_k = max(1, int(max(payload.top_k, runtime_settings.rag.top_k)))
        retrieval_top_k = min(retrieval_top_k, settings.retrieval_max_top_k)

        retrieval_result = self.embedding_service.retrieve(
            query=rewritten_query,
            top_k=retrieval_top_k,
            doc_id=payload.doc_id,
        )

        raw_hits = list(retrieval_result.get("results") or [])
        min_score = float(runtime_settings.rag.min_score)
        filtered_hits = [chunk for chunk in raw_hits if float(chunk.get("score") or 0.0) >= min_score]
        doc_ids = [chunk["doc_id"] for chunk in filtered_hits]
        title_map = self._load_document_titles(doc_ids)
        for chunk in filtered_hits:
            chunk["document_title"] = title_map.get(chunk["doc_id"], "Dokument")

        context_chunks, context_chars = self._select_context_chunks(
            filtered_hits,
            max_context_chars=int(runtime_settings.rag.max_context_chars),
        )
        context_text, _ = self._render_context(context_chunks)
        has_context = len(context_chunks) > 0

        doc_titles = self._extract_doc_titles(context_chunks)
        llm_settings = runtime_settings.llm
        if mode == "summary":
            template = llm_settings.summary_prompt_template
        elif mode == "numeric":
            template = llm_settings.numeric_prompt_template
        else:
            template = llm_settings.answer_prompt_template

        base_user_prompt = self._apply_template(
            template,
            context=context_text,
            question=question,
            doc_titles=doc_titles,
        )
        contexts_payload = [
            {
                "doc_id": str(chunk.get("doc_id") or ""),
                "chunk_id": str(chunk.get("chunk_id") or ""),
                "chunk_index": chunk.get("chunk_index"),
                "page_from": chunk.get("page_from"),
                "page_to": chunk.get("page_to"),
                "score": float(chunk.get("score") or 0.0),
                "text": str(chunk.get("text") or ""),
            }
            for chunk in context_chunks
        ]

        retries = 0
        timeout_happened = False
        llm_duration_ms = 0.0
        prompt_tokens = 0
        completion_tokens = 0
        llm_model_name = "none"
        repair_pass_used = False

        if not has_context:
            context_hint = "Bitte OCR/Index prüfen, da keine relevanten Chunks gefunden wurden."
            answer = self._build_mode_fallback(mode, context_missing_hint=context_hint, timeout=False)
        else:
            llm_result = self._call_chat_model(
                model_question=rewritten_query or question,
                chat_model=runtime_settings.ollama.chat_model,
                system_prompt=llm_settings.system_prompt,
                user_prompt=base_user_prompt,
                contexts=contexts_payload,
                temperature=float(llm_settings.temperature),
                top_p=float(llm_settings.top_p),
                max_tokens=int(llm_settings.max_output_tokens),
                timeout_seconds=settings.ai_chat_timeout_seconds,
            )
            answer = str(llm_result.get("answer") or "").strip()
            llm_duration_ms += float(llm_result.get("duration_ms") or 0.0)
            prompt_tokens += int(llm_result.get("prompt_tokens") or 0)
            completion_tokens += int(llm_result.get("completion_tokens") or 0)
            llm_model_name = str(llm_result.get("model_name") or "default")
            timeout_happened = bool(llm_result.get("timeout"))

            if not answer:
                retries += 1
                retry_chunks, _ = self._select_context_chunks(
                    context_chunks,
                    max_context_chars=max(2000, int(runtime_settings.rag.max_context_chars // 2)),
                )
                retry_context_text, _ = self._render_context(retry_chunks)
                retry_prompt = self._apply_template(
                    template,
                    context=retry_context_text,
                    question=question,
                    doc_titles=self._extract_doc_titles(retry_chunks),
                )
                retry_contexts = contexts_payload[: max(1, len(retry_chunks))]
                retry_result = self._call_chat_model(
                    model_question=rewritten_query or question,
                    system_prompt=llm_settings.system_prompt,
                    user_prompt=retry_prompt,
                    contexts=retry_contexts,
                    temperature=float(llm_settings.temperature),
                    top_p=float(llm_settings.top_p),
                    max_tokens=min(800, int(llm_settings.max_output_tokens)),
                    timeout_seconds=settings.ai_chat_timeout_seconds,
                )
                answer = str(retry_result.get("answer") or "").strip()
                llm_duration_ms += float(retry_result.get("duration_ms") or 0.0)
                prompt_tokens += int(retry_result.get("prompt_tokens") or 0)
                completion_tokens += int(retry_result.get("completion_tokens") or 0)
                llm_model_name = str(retry_result.get("model_name") or llm_model_name)
                timeout_happened = timeout_happened or bool(retry_result.get("timeout"))

            if not answer:
                answer = self._build_mode_fallback(mode, timeout=timeout_happened)

        citations = self._aggregate_citations(context_chunks, title_map, max_docs=4)
        quality_flags = self._analyze_quality_flags(
            answer,
            citations,
            mode=mode,
            repair_pass_used=repair_pass_used,
        )

        if runtime_settings.quality.enable_answer_checks and (
            quality_flags["empty_answer"] or quality_flags["numbers_without_citations"] or quality_flags["missing_citations"]
        ):
            repair_prompt = (
                "Die folgende Antwort verletzt Qualitätsregeln. "
                "Füge Belege hinzu oder entferne unbelegte Zahlen. "
                "Antworte im geforderten Format.\n\n"
                f"VORIGE_ANTWORT:\n{answer}\n\n"
                f"DOKUMENTKONTEXT:\n{context_text}\n\n"
                f"FRAGE:\n{question}"
            )
            repair_result = self._call_chat_model(
                model_question=rewritten_query or question,
                chat_model=runtime_settings.ollama.chat_model,
                system_prompt=llm_settings.system_prompt,
                user_prompt=repair_prompt,
                contexts=[
                    {
                        "doc_id": str(chunk.get("doc_id") or ""),
                        "chunk_id": str(chunk.get("chunk_id") or ""),
                        "chunk_index": chunk.get("chunk_index"),
                        "page_from": chunk.get("page_from"),
                        "page_to": chunk.get("page_to"),
                        "score": float(chunk.get("score") or 0.0),
                        "text": str(chunk.get("text") or ""),
                    }
                    for chunk in context_chunks
                ],
                temperature=float(llm_settings.temperature),
                top_p=float(llm_settings.top_p),
                max_tokens=min(900, int(llm_settings.max_output_tokens)),
                timeout_seconds=settings.ai_chat_timeout_seconds,
            )
            repaired = str(repair_result.get("answer") or "").strip()
            llm_duration_ms += float(repair_result.get("duration_ms") or 0.0)
            prompt_tokens += int(repair_result.get("prompt_tokens") or 0)
            completion_tokens += int(repair_result.get("completion_tokens") or 0)
            llm_model_name = str(repair_result.get("model_name") or llm_model_name)
            timeout_happened = timeout_happened or bool(repair_result.get("timeout"))
            if repaired:
                answer = repaired
                repair_pass_used = True
                quality_flags = self._analyze_quality_flags(
                    answer,
                    citations,
                    mode=mode,
                    repair_pass_used=repair_pass_used,
                )

        if not str(answer or "").strip():
            answer = self._build_mode_fallback(mode, timeout=False)
            quality_flags = self._analyze_quality_flags(
                answer,
                citations,
                mode=mode,
                repair_pass_used=repair_pass_used,
            )

        self._append_session_message(session_id, "user", question)
        self._append_session_message(session_id, "assistant", answer)

        retrieval_timings = retrieval_result.get("timings") or {}
        scores = [round(float(chunk.get("score") or 0.0), 4) for chunk in filtered_hits]
        best_score = max(scores) if scores else None
        total_ms = (time.perf_counter() - started_total) * 1000

        logger.info(
            "ai_ask request_id=%s mode=%s question=%r doc_id=%s retrieval_hits=%s best_score=%s context_chars=%s "
            "prompt_tokens=%s completion_tokens=%s llm_model=%s temperature=%.2f top_p=%.2f max_tokens=%s "
            "duration_ms=%.2f timeout=%s retries=%s quality=%s",
            request_id,
            mode,
            question,
            payload.doc_id,
            len(filtered_hits),
            best_score,
            context_chars,
            prompt_tokens,
            completion_tokens,
            llm_model_name,
            float(llm_settings.temperature),
            float(llm_settings.top_p),
            int(llm_settings.max_output_tokens),
            total_ms,
            timeout_happened,
            retries,
            quality_flags,
        )

        debug_chunks = [
            {
                "doc_id": chunk["doc_id"],
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("chunk_index"),
                "page_from": chunk.get("page_from"),
                "page_to": chunk.get("page_to"),
                "chunk_type": chunk.get("chunk_type"),
                "score": float(chunk.get("score") or 0.0),
                "preview": self._snippet(str(chunk.get("text") or ""), limit=140),
            }
            for chunk in context_chunks[:10]
        ]

        return {
            "answer": answer,
            "citations": citations,
            "meta": {
                "request_id": request_id,
                "session_id": str(session_id),
                "mode": mode,
                "rewritten_query": rewritten_query,
                "embed_ms": float(retrieval_timings.get("embed_ms") or 0.0),
                "db_ms": float(retrieval_timings.get("db_ms") or 0.0),
                "llm_ms": round(llm_duration_ms, 2),
                "total_ms": round(total_ms, 2),
            },
            "debug": {
                "mode": mode,
                "retrieval_model": retrieval_result.get("model") or settings.embed_model,
                "retrieval": {
                    "timings": {
                        "embed_ms": float(retrieval_timings.get("embed_ms") or 0.0),
                        "db_ms": float(retrieval_timings.get("db_ms") or 0.0),
                        "total_ms": float(retrieval_timings.get("total_ms") or 0.0),
                    },
                    "num_hits": len(filtered_hits),
                    "best_score": best_score,
                    "scores": scores[:20],
                    "chunk_ids": [str(chunk.get("chunk_id")) for chunk in context_chunks[:20]],
                    "context_chars": context_chars,
                    "chunks": debug_chunks,
                },
                "llm": {
                    "model_name": llm_model_name,
                    "temperature": float(llm_settings.temperature),
                    "top_p": float(llm_settings.top_p),
                    "max_tokens": int(llm_settings.max_output_tokens),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "duration_ms": round(llm_duration_ms, 2),
                    "timeout": timeout_happened,
                    "retries": retries,
                },
                "quality_flags": quality_flags,
                "total_ms": round(total_ms, 2),
            },
        }
