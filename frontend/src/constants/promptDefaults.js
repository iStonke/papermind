export const SYSTEM_PROMPT_DEFAULT = `Du bist ein präziser Assistent für Dokumentenanalyse.
Du darfst ausschließlich Informationen verwenden, die im bereitgestellten DOKUMENTKONTEXT stehen.
Wenn eine Information nicht im Kontext enthalten ist, sage klar: "Im Dokumentenkontext nicht enthalten."
Erfinde niemals Zahlen, Namen, Daten oder Inhalte.

WICHTIG:
- Jede Zahl, jedes Datum und jede konkrete Behauptung muss durch einen BELEG aus dem Kontext gestützt werden.
- Gib Belege als kurze Textausschnitte an und nenne die Quelle (Seite/Chunk-ID), wenn vorhanden.
- Antworte immer im definierten Format. Gib niemals eine leere Antwort.`;

export const ANSWER_PROMPT_TEMPLATE_DEFAULT = `DOKUMENTKONTEXT:
{{context}}

FRAGE:
{{question}}

ANTWORTFORMAT (immer exakt einhalten):
1) Kurzantwort (1-3 Sätze)
2) Details (Bulletpoints)
3) Belege (Bulletpoints, je Beleg: [Quelle] "Ausschnitt")
4) Unsicherheit / fehlt im Kontext (nur wenn nötig)

REGELN:
- Wenn Kontext nichts Passendes enthält: schreibe in 1) "Im Dokumentenkontext nicht enthalten." und in 4) welche Info fehlt.
- Zahlen/Datumswerte nur nennen, wenn sie in den Belegen vorkommen.`;

export const SUMMARY_PROMPT_TEMPLATE_DEFAULT = `DOKUMENTKONTEXT:
{{context}}

AUFGABE:
Erstelle eine Zusammenfassung in zwei Schritten:

SCHRITT A - EXTRAKTION (nur aus Kontext):
- Liste 8-15 Stichpunkte mit den wichtigsten Aussagen.
- Markiere Zahlen/Daten separat.
- Jeder Stichpunkt MUSS einen Beleg enthalten: [Quelle] "Ausschnitt".

SCHRITT B - ZUSAMMENFASSUNG:
- Schreibe eine strukturierte Zusammenfassung (max. 150-220 Wörter), basierend NUR auf Schritt A.

AUSGABEFORMAT:
A) Extraktion:
- ...
B) Zusammenfassung:
...`;

export const NUMERIC_PROMPT_TEMPLATE_DEFAULT = `DOKUMENTKONTEXT:
{{context}}

FRAGE:
{{question}}

AUFGABE:
Extrahiere relevante Zahlen/Einheiten/Daten exakt aus dem Kontext und beantworte die Frage.

AUSGABEFORMAT:
1) Gefundene Werte (Tabelle oder Bulletpoints):
- Wert | Einheit | Bedeutung | Quelle | Beleg-Ausschnitt
2) Interpretation / Ergebnis (1-3 Sätze)
3) Plausibilitätscheck:
- Gibt es mehrere ähnliche Werte? (ja/nein + kurzer Hinweis)
- Netto/Brutto / Preis je Einheit / Zeitraum beachtet? (kurz)

REGEL:
Wenn du keinen passenden Zahlenwert findest: "Im Dokumentenkontext nicht enthalten." + was gesucht wurde.`;

export const AVAILABLE_PROMPT_PLACEHOLDERS = ['{{context}}', '{{question}}', '{{doc_titles}}', '{{today}}'];
