from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.retention import RetentionPaperOriginal

SYSTEM_PROMPT_DEFAULT = """
Du bist ein präziser Assistent für Dokumentenanalyse.
Du darfst ausschließlich Informationen verwenden, die im bereitgestellten DOKUMENTKONTEXT stehen.
Wenn eine Information nicht im Kontext enthalten ist, sage klar: "Im Dokumentenkontext nicht enthalten."
Erfinde niemals Zahlen, Namen, Daten oder Inhalte.

WICHTIG:
- Jede Zahl, jedes Datum und jede konkrete Behauptung muss durch einen BELEG aus dem Kontext gestützt werden.
- Gib Belege als kurze Textausschnitte an und nenne die Quelle (Seite/Chunk-ID), wenn vorhanden.
- Antworte immer im definierten Format. Gib niemals eine leere Antwort.
""".strip()

ANSWER_PROMPT_TEMPLATE_DEFAULT = """
DOKUMENTKONTEXT:
{{context}}

FRAGE:
{{question}}

ANTWORTFORMAT (immer exakt einhalten):
1) Kurzantwort (1–3 Sätze)
2) Details (Bulletpoints)
3) Belege (Bulletpoints, je Beleg: [Quelle] "Ausschnitt")
4) Unsicherheit / fehlt im Kontext (nur wenn nötig)

REGELN:
- Wenn Kontext nichts Passendes enthält: schreibe in 1) "Im Dokumentenkontext nicht enthalten." und in 4) welche Info fehlt.
- Zahlen/Datumswerte nur nennen, wenn sie in den Belegen vorkommen.
""".strip()

SUMMARY_PROMPT_TEMPLATE_DEFAULT = """
DOKUMENTKONTEXT:
{{context}}

AUFGABE:
Erstelle eine Zusammenfassung in zwei Schritten:

SCHRITT A — EXTRAKTION (nur aus Kontext):
- Liste 8–15 Stichpunkte mit den wichtigsten Aussagen.
- Markiere Zahlen/Daten separat.
- Jeder Stichpunkt MUSS einen Beleg enthalten: [Quelle] "Ausschnitt".

SCHRITT B — ZUSAMMENFASSUNG:
- Schreibe eine strukturierte Zusammenfassung (max. 150–220 Wörter), basierend NUR auf Schritt A.

AUSGABEFORMAT:
A) Extraktion:
- ...
B) Zusammenfassung:
...
""".strip()

NUMERIC_PROMPT_TEMPLATE_DEFAULT = """
DOKUMENTKONTEXT:
{{context}}

FRAGE:
{{question}}

AUFGABE:
Extrahiere relevante Zahlen/Einheiten/Daten exakt aus dem Kontext und beantworte die Frage.

AUSGABEFORMAT:
1) Gefundene Werte (Tabelle oder Bulletpoints):
- Wert | Einheit | Bedeutung | Quelle | Beleg-Ausschnitt
2) Interpretation / Ergebnis (1–3 Sätze)
3) Plausibilitätscheck:
- Gibt es mehrere ähnliche Werte? (ja/nein + kurzer Hinweis)
- Netto/Brutto / Preis je Einheit / Zeitraum beachtet? (kurz)

REGEL:
Wenn du keinen passenden Zahlenwert findest: "Im Dokumentenkontext nicht enthalten." + was gesucht wurde.
""".strip()


class ThemeMode(str, Enum):
    light = "light"
    dark = "dark"
    system = "system"


class ColorVariant(str, Enum):
    teal = "teal"
    violet = "violet"
    blue = "blue"


class DocumentSortOrder(str, Enum):
    newest = "newest"
    oldest = "oldest"
    document_date_desc = "document_date_desc"
    document_date_asc = "document_date_asc"
    name_asc = "name_asc"
    name_desc = "name_desc"
    last_opened = "last_opened"


class OCREngine(str, Enum):
    tesseract = "tesseract"
    paddleocr = "paddleocr"
    easyocr = "easyocr"
    abbyy = "abbyy"


class SidebarSectionKey(str, Enum):
    ordner = "ordner"
    tags = "tags"
    kategorien = "kategorien"


# Reihenfolge entspricht der Standard-Anzeigereihenfolge in der Seitenleiste.
SIDEBAR_SECTION_KEYS: tuple[str, ...] = ("ordner", "tags", "kategorien")


class SidebarSectionConfig(BaseModel):
    key: SidebarSectionKey
    visible: bool = True


def _default_sidebar_sections() -> list[SidebarSectionConfig]:
    return [SidebarSectionConfig(key=SidebarSectionKey(key)) for key in SIDEBAR_SECTION_KEYS]


def _normalize_sidebar_sections(
    sections: list[SidebarSectionConfig] | None,
) -> list[SidebarSectionConfig]:
    """Dedupliziert nach Key (erstes Vorkommen gewinnt) und ergänzt fehlende
    Sektionen in der Standardreihenfolge, sodass immer genau alle bekannten
    Sektionen vorhanden sind."""
    result: list[SidebarSectionConfig] = []
    seen: set[str] = set()
    for section in sections or []:
        key = section.key.value
        if key in seen:
            continue
        seen.add(key)
        result.append(section)
    for key in SIDEBAR_SECTION_KEYS:
        if key not in seen:
            result.append(SidebarSectionConfig(key=SidebarSectionKey(key)))
    return result


class UISettingsRead(BaseModel):
    theme_mode: ThemeMode = ThemeMode.system
    color_variant: ColorVariant = ColorVariant.teal
    showFilenameSuffix: bool = True
    drawerRememberState: bool = True
    tagDrawerRememberState: bool = True
    sidebar_show_recent: bool = True
    sidebar_show_untagged: bool = True
    sidebar_show_no_text: bool = True
    sidebar_show_chat: bool = True
    sidebar_sections: list[SidebarSectionConfig] = Field(default_factory=_default_sidebar_sections)
    # Max. Anzahl der Quicklinks pro Sektion in der Seitenleiste (0 = nur „Alle …").
    sidebar_max_tags: int = Field(default=5, ge=0, le=50)
    sidebar_max_categories: int = Field(default=5, ge=0, le=50)

    @model_validator(mode="after")
    def normalize_sidebar_sections(self) -> "UISettingsRead":
        self.sidebar_sections = _normalize_sidebar_sections(self.sidebar_sections)
        return self


class DocumentsSettingsRead(BaseModel):
    auto_ocr: bool = True
    auto_tagging: bool = False
    ocr_backfill_enabled: bool = True
    auto_open_import_inbox: bool = False
    sort_order: DocumentSortOrder = DocumentSortOrder.newest
    recent_import_window_hours: int = Field(default=24, ge=1)
    trash_retention_days: int = Field(default=30, ge=0, le=365)


class LLMSettingsRead(BaseModel):
    system_prompt: str = Field(default=SYSTEM_PROMPT_DEFAULT, min_length=50, max_length=12000)
    answer_prompt_template: str = Field(default=ANSWER_PROMPT_TEMPLATE_DEFAULT, min_length=50, max_length=20000)
    summary_prompt_template: str = Field(default=SUMMARY_PROMPT_TEMPLATE_DEFAULT, min_length=50, max_length=24000)
    numeric_prompt_template: str = Field(default=NUMERIC_PROMPT_TEMPLATE_DEFAULT, min_length=50, max_length=24000)
    temperature: float = Field(default=0.15, ge=0.0, le=1.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=1200, ge=256, le=4096)
    embedding_model_name: str = Field(default="hash-384-v1", min_length=3, max_length=128)


class RAGSettingsRead(BaseModel):
    top_k: int = Field(default=8, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    max_context_chars: int = Field(default=12000, ge=4000, le=40000)
    chunk_chars: int = Field(default=4500, ge=600, le=20000)
    chunk_overlap_chars: int = Field(default=600, ge=0, le=10000)
    rerank_enabled: bool = False
    rerank_top_k: int = Field(default=20, ge=8, le=100)
    rerank_final_k: int = Field(default=8, ge=1, le=50)

    @model_validator(mode="after")
    def validate_chunking_rules(self) -> "RAGSettingsRead":
        if self.chunk_overlap_chars >= self.chunk_chars:
            raise ValueError("rag.chunk_overlap_chars must be smaller than rag.chunk_chars")
        if self.rerank_final_k > self.rerank_top_k:
            raise ValueError("rag.rerank_final_k must be <= rag.rerank_top_k")
        return self


class OCRSettingsRead(BaseModel):
    engine: OCREngine = OCREngine.tesseract
    language: str = Field(default="deu+eng", min_length=2, max_length=24)
    enable_layout: bool = True
    enable_table_detection: bool = True
    deskew: bool = True
    denoise: bool = True
    use_unpaper: bool = True
    dpi_target: int = Field(default=300, ge=150, le=600)
    postprocess_hyphenation: bool = True
    remove_headers_footers: bool = True

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip().lower()
        if not normalized:
            raise ValueError("ocr.language must not be empty")
        return normalized


class QualitySettingsRead(BaseModel):
    enable_answer_checks: bool = True
    enable_self_critique: bool = False


class OllamaSettingsRead(BaseModel):
    enabled: bool = False
    base_url: str = Field(default="http://localhost:11434", max_length=256)
    model: str = Field(default="llama3.2:3b", max_length=128)
    # Model used for the Q&A chat / RAG answers. Separate from `model` (which is
    # used for import metadata extraction) so users can trade quality vs. speed.
    chat_model: str = Field(default="llama3.2:3b", max_length=128)
    timeout_seconds: float = Field(default=90.0, ge=10.0, le=300.0)
    max_input_chars: int = Field(default=800, ge=200, le=4000)


RetentionUsageMode = Literal["private", "business"]


class RetentionRule(BaseModel):
    document_type: str = Field(max_length=64)
    paper_original: RetentionPaperOriginal = RetentionPaperOriginal.unclear
    period_years: int | None = Field(default=None, ge=-1, le=100)
    basis: str = Field(default="", max_length=200)

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise ValueError("document_type must not be empty")
        return normalized

    @field_validator("basis")
    @classmethod
    def normalize_basis(cls, value: str) -> str:
        return " ".join(str(value or "").split()).strip()


class RetentionSettingsRead(BaseModel):
    enabled: bool = True
    usage_mode: RetentionUsageMode = "business"
    rules: list[RetentionRule] = Field(default_factory=list)


class SettingsMetaRead(BaseModel):
    version: int = Field(default=1, ge=1)
    updated_at: datetime | None = None


class AppSettingsRead(BaseModel):
    ui: UISettingsRead = Field(default_factory=UISettingsRead)
    documents: DocumentsSettingsRead = Field(default_factory=DocumentsSettingsRead)
    llm: LLMSettingsRead = Field(default_factory=LLMSettingsRead)
    rag: RAGSettingsRead = Field(default_factory=RAGSettingsRead)
    ocr: OCRSettingsRead = Field(default_factory=OCRSettingsRead)
    quality: QualitySettingsRead = Field(default_factory=QualitySettingsRead)
    ollama: OllamaSettingsRead = Field(default_factory=OllamaSettingsRead)
    retention: RetentionSettingsRead = Field(default_factory=RetentionSettingsRead)
    meta: SettingsMetaRead = Field(default_factory=SettingsMetaRead)


class UISettingsPatch(BaseModel):
    theme_mode: ThemeMode | None = None
    color_variant: ColorVariant | None = None
    showFilenameSuffix: bool | None = None
    drawerRememberState: bool | None = None
    tagDrawerRememberState: bool | None = None
    sidebar_show_recent: bool | None = None
    sidebar_show_untagged: bool | None = None
    sidebar_show_no_text: bool | None = None
    sidebar_show_chat: bool | None = None
    sidebar_sections: list[SidebarSectionConfig] | None = None
    sidebar_max_tags: int | None = Field(default=None, ge=0, le=50)
    sidebar_max_categories: int | None = Field(default=None, ge=0, le=50)

    @field_validator("sidebar_sections")
    @classmethod
    def normalize_sidebar_sections(
        cls, value: list[SidebarSectionConfig] | None
    ) -> list[SidebarSectionConfig] | None:
        if value is None:
            return None
        return _normalize_sidebar_sections(value)


class DocumentsSettingsPatch(BaseModel):
    auto_ocr: bool | None = None
    auto_tagging: bool | None = None
    ocr_backfill_enabled: bool | None = None
    auto_open_import_inbox: bool | None = None
    sort_order: DocumentSortOrder | None = None
    recent_import_window_hours: int | None = Field(default=None, ge=1)
    trash_retention_days: int | None = Field(default=None, ge=0, le=365)


class LLMSettingsPatch(BaseModel):
    system_prompt: str | None = Field(default=None, min_length=50, max_length=12000)
    answer_prompt_template: str | None = Field(default=None, min_length=50, max_length=20000)
    summary_prompt_template: str | None = Field(default=None, min_length=50, max_length=24000)
    numeric_prompt_template: str | None = Field(default=None, min_length=50, max_length=24000)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_output_tokens: int | None = Field(default=None, ge=256, le=4096)
    embedding_model_name: str | None = Field(default=None, min_length=3, max_length=128)


class RAGSettingsPatch(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_context_chars: int | None = Field(default=None, ge=4000, le=40000)
    chunk_chars: int | None = Field(default=None, ge=600, le=20000)
    chunk_overlap_chars: int | None = Field(default=None, ge=0, le=10000)
    rerank_enabled: bool | None = None
    rerank_top_k: int | None = Field(default=None, ge=8, le=100)
    rerank_final_k: int | None = Field(default=None, ge=1, le=50)


class OCRSettingsPatch(BaseModel):
    engine: OCREngine | None = None
    language: str | None = Field(default=None, min_length=2, max_length=24)
    enable_layout: bool | None = None
    enable_table_detection: bool | None = None
    deskew: bool | None = None
    denoise: bool | None = None
    use_unpaper: bool | None = None
    dpi_target: int | None = Field(default=None, ge=150, le=600)
    postprocess_hyphenation: bool | None = None
    remove_headers_footers: bool | None = None

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip().lower()
        if not normalized:
            raise ValueError("ocr.language must not be empty")
        return normalized


class QualitySettingsPatch(BaseModel):
    enable_answer_checks: bool | None = None
    enable_self_critique: bool | None = None


class SettingsMetaPatch(BaseModel):
    version: int | None = Field(default=None, ge=1)


class OllamaSettingsPatch(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=256)
    model: str | None = Field(default=None, max_length=128)
    chat_model: str | None = Field(default=None, max_length=128)
    timeout_seconds: float | None = Field(default=None, ge=10.0, le=300.0)
    max_input_chars: int | None = Field(default=None, ge=200, le=4000)


class RetentionSettingsPatch(BaseModel):
    enabled: bool | None = None
    usage_mode: RetentionUsageMode | None = None
    rules: list[RetentionRule] | None = None


class AppSettingsPatch(BaseModel):
    ui: UISettingsPatch | None = None
    documents: DocumentsSettingsPatch | None = None
    llm: LLMSettingsPatch | None = None
    rag: RAGSettingsPatch | None = None
    ocr: OCRSettingsPatch | None = None
    quality: QualitySettingsPatch | None = None
    ollama: OllamaSettingsPatch | None = None
    retention: RetentionSettingsPatch | None = None
    meta: SettingsMetaPatch | None = None
