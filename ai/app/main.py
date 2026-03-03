import hashlib
import logging
import math
import os
import re
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("papermind.ai")
logging.basicConfig(level=logging.INFO)

EMBED_MODEL = os.getenv("EMBED_MODEL", "hash-384-v1").strip() or "hash-384-v1"
EMBED_DIM = max(8, int(os.getenv("EMBED_DIM", "384")))
EMBED_MAX_TEXTS = max(1, int(os.getenv("EMBED_MAX_TEXTS", "64")))
EMBED_MAX_CHARS = max(64, int(os.getenv("EMBED_MAX_CHARS", "4000")))
GERMAN_STOPWORDS = {
    "der",
    "die",
    "das",
    "den",
    "dem",
    "des",
    "ein",
    "eine",
    "einer",
    "eines",
    "ist",
    "sind",
    "war",
    "wie",
    "was",
    "welche",
    "welcher",
    "welches",
    "und",
    "oder",
    "mit",
    "ohne",
    "von",
    "zu",
    "im",
    "in",
    "am",
    "an",
    "auf",
    "für",
    "als",
    "nach",
    "vor",
    "bei",
    "gilt",
    "steht",
}


class EmbedRequest(BaseModel):
    model: str = Field(default="default")
    texts: list[str] = Field(default_factory=list)


class EmbedResponse(BaseModel):
    model: str
    dim: int
    vectors: list[list[float]]


class ChatContext(BaseModel):
    doc_id: str | None = None
    chunk_id: str | None = None
    chunk_index: int | None = None
    page_from: int | None = None
    page_to: int | None = None
    score: float | None = None
    text: str = Field(default="")


class ChatRequest(BaseModel):
    model: str = Field(default="default")
    system_prompt: str | None = None
    max_sentences: int = Field(default=8, ge=1, le=12)
    max_tokens: int = Field(default=180, ge=32, le=4096)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    user_prompt: str | None = None
    question: str = Field(min_length=1, max_length=4000)
    contexts: list[ChatContext] = Field(default_factory=list)


class ChatResponse(BaseModel):
    model: str
    answer: str
    used_contexts: int


NO_INFO_ANSWER = "Dazu finde ich keine Information in den Dokumenten."


def _normalize_text(value: str) -> str:
    text_value = " ".join(str(value or "").split())
    return text_value.strip()


def _hash_embed(text_value: str) -> list[float]:
    normalized = _normalize_text(text_value).lower()
    tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
    if not tokens and normalized:
        tokens = [normalized]

    vector = [0.0] * EMBED_DIM
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        idx1 = int.from_bytes(digest[0:4], "big") % EMBED_DIM
        idx2 = int.from_bytes(digest[4:8], "big") % EMBED_DIM
        sign1 = 1.0 if digest[8] & 1 else -1.0
        sign2 = 1.0 if digest[9] & 1 else -1.0
        vector[idx1] += sign1
        vector[idx2] += sign2 * 0.5

    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def _tokenize(value: str) -> list[str]:
    return re.findall(r"\w+", _normalize_text(value).lower(), flags=re.UNICODE)


def _question_tokens(value: str) -> set[str]:
    tokens = _tokenize(value)
    strong = [token for token in tokens if len(token) >= 4 and token not in GERMAN_STOPWORDS]
    if strong:
        return set(strong)
    weak = [token for token in tokens if len(token) >= 3 and token not in GERMAN_STOPWORDS]
    return set(weak)


def _detect_question_mode(question: str) -> str:
    lower = _normalize_text(question).lower()
    if any(token in lower for token in ("iban", "bic", "bankverbindung", "kontodaten", "kontoinhaber", "sepa", "bank")):
        return "bank_details"
    if any(
        token in lower
        for token in (
            "betrag",
            "summe",
            "gesamtsumme",
            "gesamtbetrag",
            "kosten",
            "gekostet",
            "bezahlen",
            "bezahlt",
            "zu zahlen",
            "wie viel",
            "wieviel",
            "was musste ich",
            "wie hoch",
            "preis",
        )
    ):
        return "amount"
    if any(token in lower for token in ("wann", "datum", "fällig", "frist", "zeitpunkt")):
        return "date"
    if any(token in lower for token in ("wo", "adresse", "ort", "standort")):
        return "location"
    if any(token in lower for token in ("wie heißt", "name", "wer", "an wen")):
        return "name"
    return "general"


def _format_amount(value: str) -> str:
    cleaned = value.replace(" ", "")
    if re.fullmatch(r"\d+\.\d{2}", cleaned):
        cleaned = cleaned.replace(".", ",")
    return cleaned


def _amount_to_float(value: str) -> float:
    cleaned = value.replace(" ", "")
    if "," in cleaned:
        numeric = cleaned.replace(".", "").replace(",", ".")
    else:
        numeric = cleaned
    try:
        return float(numeric)
    except ValueError:
        return 0.0


def _extract_amount(contexts: list[ChatContext], prefer_highest: bool = False) -> str | None:
    keyword_weights = (
        ("gesamtbetrag", 12),
        ("gesamtsumme", 12),
        ("endbetrag", 11),
        ("rechnungsbetrag", 10),
        ("inkl. mwst", 10),
        ("inkl mwst", 10),
        ("brutto", 10),
        ("total", 9),
        ("summe", 6),
        ("betrag", 4),
    )
    amount_pattern = r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b|\b\d+\.\d{2}\b"
    candidates: list[tuple[int, float, str]] = []

    for context in contexts:
        text_value = _normalize_text(context.text)
        if not text_value:
            continue
        lower = text_value.lower()
        for match in re.finditer(amount_pattern, text_value):
            raw_value = match.group(0)
            numeric = _amount_to_float(raw_value)
            if numeric <= 0:
                continue

            window_start = max(0, match.start() - 140)
            window_end = min(len(text_value), match.end() + 30)
            window = lower[window_start:window_end]

            boost = 0
            for keyword, weight in keyword_weights:
                if keyword in window:
                    boost += weight

            candidates.append((boost, numeric, _format_amount(raw_value)))

    if not candidates:
        return None

    if prefer_highest:
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[0][2]

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _extract_date(contexts: list[ChatContext]) -> str | None:
    patterns = [
        r"\b\d{2}\.\d{2}\.\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ]
    for context in contexts:
        text_value = _normalize_text(context.text)
        if not text_value:
            continue
        for pattern in patterns:
            match = re.search(pattern, text_value)
            if match:
                return match.group(0)
    return None


def _extract_name(contexts: list[ChatContext]) -> str | None:
    name_patterns = [
        r"\b(?:Herr|Herrn|Frau)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1})\b",
        r"\bName\s*:\s*([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3})\b",
    ]
    for context in contexts:
        text_value = _normalize_text(context.text)
        if not text_value:
            continue
        for pattern in name_patterns:
            match = re.search(pattern, text_value)
            if match:
                return match.group(1).strip()
    return None


def _extract_location(contexts: list[ChatContext]) -> str | None:
    city_pattern = re.compile(r"\b(\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)\b")
    street_tail_pattern = re.compile(
        r"([A-Za-zÄÖÜäöüß.\-]{3,}(?:\s+[A-Za-zÄÖÜäöüß.\-]{2,}){0,2}\s+\d{1,4}[a-zA-Z]?)\s*$"
    )
    honorifics = {"herr", "herrn", "frau"}

    for context in contexts:
        text_value = _normalize_text(context.text)
        if not text_value:
            continue

        city_match = city_pattern.search(text_value)
        if city_match:
            city = _normalize_text(city_match.group(1))
            prefix = _normalize_text(text_value[: city_match.start()])
            tail = prefix[-96:]
            street_match = street_tail_pattern.search(tail)
            if street_match:
                street = _normalize_text(street_match.group(1))
                street_tokens = street.split()
                if street_tokens and street_tokens[0].lower() in honorifics and len(street_tokens) >= 2:
                    street = " ".join(street_tokens[-2:])
                return f"{street}, {city}"
            return city
    return None


def _extract_bank_details(contexts: list[ChatContext]) -> tuple[str | None, str | None]:
    iban_de = re.compile(r"\bDE\d{2}[ ]?(?:\d{4}[ ]?){4}\d{2}\b", re.IGNORECASE)
    iban_generic = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
    bic_de = re.compile(r"\b[A-Z]{4}DE[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", re.IGNORECASE)
    bic_generic = re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", re.IGNORECASE)

    iban: str | None = None
    bic: str | None = None

    for context in contexts:
        text_value = _normalize_text(context.text)
        if not text_value:
            continue
        if iban is None:
            match = iban_de.search(text_value) or iban_generic.search(text_value)
            if match:
                iban = " ".join(re.findall(r".{1,4}", re.sub(r"\s+", "", match.group(0).upper())))
        if bic is None:
            match = bic_de.search(text_value) or bic_generic.search(text_value)
            if match:
                bic = _normalize_text(match.group(0).upper())
        if iban and bic:
            break
    return iban, bic


def _build_mode_answer(mode: str, question: str, contexts: list[ChatContext]) -> str | None:
    if mode == "amount":
        lower_question = _normalize_text(question).lower()
        prefer_highest = any(token in lower_question for token in ("rechnung", "gesamt", "summe", "total", "insgesamt", "wie hoch"))
        value = _extract_amount(contexts, prefer_highest=prefer_highest)
        if value:
            return f"Der Betrag beträgt {value} €."
        return NO_INFO_ANSWER
    if mode == "date":
        value = _extract_date(contexts)
        if value:
            return f"Das Datum ist {value}."
        return NO_INFO_ANSWER
    if mode == "name":
        value = _extract_name(contexts)
        if value:
            return f"Der Name lautet {value}."
        return NO_INFO_ANSWER
    if mode == "location":
        value = _extract_location(contexts)
        if value:
            return f"Der Ort ist {value}."
        return NO_INFO_ANSWER
    if mode == "bank_details":
        iban, bic = _extract_bank_details(contexts)
        if iban:
            if bic:
                return f"IBAN: {iban}\nBIC: {bic}"
            return f"IBAN: {iban}"
        return "Ich finde keine IBAN in den Dokumenten."
    return None


def _sentence_split(text_value: str) -> list[str]:
    normalized = _normalize_text(text_value)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _score_sentence(question_tokens: set[str], sentence: str) -> float:
    sentence_tokens = _tokenize(sentence)
    if not sentence_tokens:
        return 0.0
    overlap = sum(1 for token in sentence_tokens if token in question_tokens)
    if overlap == 0:
        return 0.0
    diversity = len(set(sentence_tokens))
    return float(overlap) + min(diversity / 50.0, 0.8)


def _clamp_sentences(value: int) -> int:
    return max(1, min(int(value or 8), 12))


def _build_chat_answer(question: str, contexts: list[ChatContext], max_sentences: int) -> str:
    mode = _detect_question_mode(question)
    mode_answer = _build_mode_answer(mode, question, contexts)
    if mode_answer:
        return mode_answer

    sentence_limit = _clamp_sentences(max_sentences)
    question_tokens = _question_tokens(question)
    if not question_tokens:
        return NO_INFO_ANSWER
    candidate_sentences: list[tuple[float, str]] = []

    for context in contexts:
        for sentence in _sentence_split(context.text):
            if len(sentence) > 240:
                continue
            score = _score_sentence(question_tokens, sentence)
            if score <= 0:
                continue
            candidate_sentences.append((score, sentence))

    if not candidate_sentences:
        return NO_INFO_ANSWER

    candidate_sentences.sort(key=lambda item: item[0], reverse=True)
    selected: list[str] = []
    seen = set()
    for _, sentence in candidate_sentences:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(sentence)
        if len(selected) >= sentence_limit:
            break

    if not selected:
        return NO_INFO_ANSWER

    return " ".join(selected)


app = FastAPI(title="PaperMind AI Service", version="0.2.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai", "model": EMBED_MODEL, "dim": EMBED_DIM}


@app.post("/embed", response_model=EmbedResponse)
async def embed(payload: EmbedRequest) -> Any:
    texts = payload.texts or []
    if not texts:
        raise HTTPException(status_code=400, detail="texts must not be empty")
    if len(texts) > EMBED_MAX_TEXTS:
        raise HTTPException(
            status_code=400,
            detail=f"texts exceeds max batch size ({EMBED_MAX_TEXTS})",
        )

    normalized_texts: list[str] = []
    total_chars = 0
    for text_item in texts:
        normalized = _normalize_text(text_item)
        if len(normalized) > EMBED_MAX_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"text exceeds max chars ({EMBED_MAX_CHARS})",
            )
        normalized_texts.append(normalized)
        total_chars += len(normalized)

    started = time.perf_counter()
    vectors = [_hash_embed(text_item) for text_item in normalized_texts]
    elapsed_ms = (time.perf_counter() - started) * 1000
    model_name = EMBED_MODEL if payload.model in ("", "default") else payload.model.strip() or EMBED_MODEL

    logger.info(
        "embed request model=%s n_texts=%s total_chars=%s dim=%s time_ms=%.2f",
        model_name,
        len(normalized_texts),
        total_chars,
        EMBED_DIM,
        elapsed_ms,
    )

    return EmbedResponse(model=model_name, dim=EMBED_DIM, vectors=vectors)


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> Any:
    question = _normalize_text(payload.question)
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    contexts = payload.contexts or []
    started = time.perf_counter()
    answer = _build_chat_answer(question, contexts, payload.max_sentences)
    elapsed_ms = (time.perf_counter() - started) * 1000
    model_name = payload.model.strip() if payload.model and payload.model.strip() else EMBED_MODEL

    logger.info(
        "chat request model=%s question_len=%s contexts=%s time_ms=%.2f",
        model_name,
        len(question),
        len(contexts),
        elapsed_ms,
    )

    return ChatResponse(model=model_name, answer=answer, used_contexts=len(contexts))
