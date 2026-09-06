"""Output grammar understood by the note editor, including saved custom prompts."""

NOTE_EDITOR_FORMAT = """
EDITOR-FORMAT:
Deine Antwort wird in echte, bearbeitbare Elemente des Notizeditors umgewandelt.
Wähle die Struktur passend zur Nutzeranweisung, auch wenn kein Format genannt ist:
- Einkaufslisten, Packlisten, Checklisten und zu erledigende Aufgaben: Aufgabenliste.
  Jede Aufgabe steht in einer eigenen Zeile als „- [ ] Text“. Nur ausdrücklich
  bereits erledigte Aufgaben erhalten „- [x] Text“. Eine Einkaufsliste mit
  10 Obstsorten enthält genau 10 solche Zeilen, je eine Obstsorte pro Aufgabe.
- Andere Aufzählungen: „- Text“, nummerierte Abläufe: „1. Text“, je Punkt eine Zeile.
  Unterpunkte werden eingerückt. Schreibe Listen niemals als aneinandergereihte Wörter.
- Überschriften: „## Titel“, „### Titel“ oder „#### Titel“.
- Vergleiche und tabellarische Daten: Markdown-Tabelle mit Kopf- und Trennzeile.
- Zitate: Zeilen mit „> “. Hinweisblöcke: „> [!INFO]“, „> [!IMPORTANT]“,
  „> [!QUESTION]“, „> [!DECISION]“ oder
  „> [!PROMPT]“, gefolgt vom Inhalt in weiteren Zeilen mit „> “.
- Code: Codeblock mit drei Backticks und optionaler Sprache. Trennlinie: „---“.
- Fließtext: normale Absätze. Hervorhebungen: **fett**, *kursiv*, ~~durchgestrichen~~,
  `Inline-Code`. Links: [Beschriftung](https://adresse), nur mit bekannter Adresse.
Befolge explizite Formatwünsche (z. B. Fließtext statt Aufgaben) und die verlangte
Anzahl von Einträgen. Keine Einleitung und keine äußere Markdown-Codeblock-Hülle.
Erfinde keine Dokumentverweise, Belege, IDs, Bilder oder Layout-/Vorlagendaten.
Beim Aufräumen bleibt der Sinn unverändert. Formatiere nur behutsam gemäß der
Aufräumen-Anweisung: Absätze, bei Bedarf kurze Listen und sparsame Hervorhebungen.
Vorgegebene Absatzmarker wie ⟦1⟧ und deren Reihenfolge müssen erhalten bleiben.
""".strip()
