"""extend global settings with llm/rag/ocr/quality defaults

Revision ID: 022_settings_ai_ocr_quality
Revises: 021_recent_import_window
Create Date: 2026-03-02 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022_settings_ai_ocr_quality"
down_revision: Union[str, None] = "021_recent_import_window"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = COALESCE(settings_json, '{}'::jsonb)
          || jsonb_build_object(
            'ui',
            jsonb_build_object(
              'theme_mode', 'system',
              'showFilenameSuffix', true,
              'drawerRememberState', true,
              'drawerAlwaysExpanded', false
            ) || COALESCE(settings_json->'ui', '{}'::jsonb),
            'documents',
            jsonb_build_object(
              'auto_ocr', true,
              'auto_tagging', false,
              'sort_order', 'newest',
              'recent_import_window_hours', 24
            ) || COALESCE(settings_json->'documents', '{}'::jsonb),
            'llm',
            jsonb_build_object(
              'system_prompt',
              'Du bist ein präziser Assistent für Dokumentenanalyse. Du darfst ausschließlich Informationen verwenden, die im bereitgestellten DOKUMENTKONTEXT stehen. Wenn eine Information nicht im Kontext enthalten ist, sage klar: "Im Dokumentenkontext nicht enthalten." Erfinde niemals Zahlen, Namen, Daten oder Inhalte. WICHTIG: - Jede Zahl, jedes Datum und jede konkrete Behauptung muss durch einen BELEG aus dem Kontext gestützt werden. - Gib Belege als kurze Textausschnitte an und nenne die Quelle (Seite/Chunk-ID), wenn vorhanden. - Antworte immer im definierten Format. Gib niemals eine leere Antwort.',
              'answer_prompt_template',
              'DOKUMENTKONTEXT:\n{{context}}\n\nFRAGE:\n{{question}}\n\nANTWORTFORMAT (immer exakt einhalten):\n1) Kurzantwort (1–3 Sätze)\n2) Details (Bulletpoints)\n3) Belege (Bulletpoints, je Beleg: [Quelle] "Ausschnitt")\n4) Unsicherheit / fehlt im Kontext (nur wenn nötig)\n\nREGELN:\n- Wenn Kontext nichts Passendes enthält: schreibe in 1) "Im Dokumentenkontext nicht enthalten." und in 4) welche Info fehlt.\n- Zahlen/Datumswerte nur nennen, wenn sie in den Belegen vorkommen.',
              'summary_prompt_template',
              'DOKUMENTKONTEXT:\n{{context}}\n\nAUFGABE:\nErstelle eine Zusammenfassung in zwei Schritten:\n\nSCHRITT A — EXTRAKTION (nur aus Kontext):\n- Liste 8–15 Stichpunkte mit den wichtigsten Aussagen.\n- Markiere Zahlen/Daten separat.\n- Jeder Stichpunkt MUSS einen Beleg enthalten: [Quelle] "Ausschnitt".\n\nSCHRITT B — ZUSAMMENFASSUNG:\n- Schreibe eine strukturierte Zusammenfassung (max. 150–220 Wörter), basierend NUR auf Schritt A.\n\nAUSGABEFORMAT:\nA) Extraktion:\n- ...\nB) Zusammenfassung:\n...',
              'numeric_prompt_template',
              'DOKUMENTKONTEXT:\n{{context}}\n\nFRAGE:\n{{question}}\n\nAUFGABE:\nExtrahiere relevante Zahlen/Einheiten/Daten exakt aus dem Kontext und beantworte die Frage.\n\nAUSGABEFORMAT:\n1) Gefundene Werte (Tabelle oder Bulletpoints):\n- Wert | Einheit | Bedeutung | Quelle | Beleg-Ausschnitt\n2) Interpretation / Ergebnis (1–3 Sätze)\n3) Plausibilitätscheck:\n- Gibt es mehrere ähnliche Werte? (ja/nein + kurzer Hinweis)\n- Netto/Brutto / Preis je Einheit / Zeitraum beachtet? (kurz)\n\nREGEL:\nWenn du keinen passenden Zahlenwert findest: "Im Dokumentenkontext nicht enthalten." + was gesucht wurde.',
              'temperature', 0.15,
              'top_p', 0.9,
              'max_output_tokens', 1200,
              'embedding_model_name', 'hash-384-v1'
            ) || COALESCE(settings_json->'llm', '{}'::jsonb),
            'rag',
            jsonb_build_object(
              'top_k', 8,
              'min_score', 0.0,
              'max_context_chars', 12000,
              'chunk_chars', 4500,
              'chunk_overlap_chars', 600,
              'rerank_enabled', false,
              'rerank_top_k', 20,
              'rerank_final_k', 8
            ) || COALESCE(settings_json->'rag', '{}'::jsonb),
            'ocr',
            jsonb_build_object(
              'engine', 'tesseract',
              'language', 'deu',
              'enable_layout', true,
              'enable_table_detection', true,
              'deskew', true,
              'denoise', true,
              'dpi_target', 300,
              'postprocess_hyphenation', true,
              'remove_headers_footers', true
            ) || COALESCE(settings_json->'ocr', '{}'::jsonb),
            'quality',
            jsonb_build_object(
              'enable_answer_checks', true,
              'enable_self_critique', false
            ) || COALESCE(settings_json->'quality', '{}'::jsonb),
            'meta',
            jsonb_build_object(
              'version',
              GREATEST(1, COALESCE((settings_json->'meta'->>'version')::int, 1))
            ) || COALESCE(settings_json->'meta', '{}'::jsonb)
          )
        WHERE id = 1;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = COALESCE(settings_json, '{}'::jsonb)
          - 'llm'
          - 'rag'
          - 'ocr'
          - 'quality'
          - 'meta'
        WHERE id = 1;
        """
    )
