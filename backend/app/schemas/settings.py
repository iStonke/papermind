from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

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


class DocumentSortOrder(str, Enum):
    newest = "newest"
    oldest = "oldest"
    name_asc = "name_asc"
    name_desc = "name_desc"
    last_opened = "last_opened"


class OCREngine(str, Enum):
    tesseract = "tesseract"
    paddleocr = "paddleocr"
    easyocr = "easyocr"
    abbyy = "abbyy"


class UISettingsRead(BaseModel):
    theme_mode: ThemeMode = ThemeMode.system
    showFilenameSuffix: bool = True
    drawerRememberState: bool = True
    drawerAlwaysExpanded: bool = False


class DocumentsSettingsRead(BaseModel):
    auto_ocr: bool = True
    auto_tagging: bool = False
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
    language: str = Field(default="deu", min_length=2, max_length=24)
    enable_layout: bool = True
    enable_table_detection: bool = True
    deskew: bool = True
    denoise: bool = True
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
    meta: SettingsMetaRead = Field(default_factory=SettingsMetaRead)


class UISettingsPatch(BaseModel):
    theme_mode: ThemeMode | None = None
    showFilenameSuffix: bool | None = None
    drawerRememberState: bool | None = None
    drawerAlwaysExpanded: bool | None = None


class DocumentsSettingsPatch(BaseModel):
    auto_ocr: bool | None = None
    auto_tagging: bool | None = None
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


class AppSettingsPatch(BaseModel):
    ui: UISettingsPatch | None = None
    documents: DocumentsSettingsPatch | None = None
    llm: LLMSettingsPatch | None = None
    rag: RAGSettingsPatch | None = None
    ocr: OCRSettingsPatch | None = None
    quality: QualitySettingsPatch | None = None
    meta: SettingsMetaPatch | None = None
