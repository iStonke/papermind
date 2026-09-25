# PaperMind – Lernbereich: Anforderungen / Leistungsumfang

*Scope-Dokument, bewusst UI-arm. Beschreibt, **was** der Lernbereich können muss,
nicht wie er aussieht. Grundlage: `lernbereich-konzept.md` (Warum) und
`lernbereich-datenmodell.md` (Wie technisch). Stand 21.09.2026.*

---

## 0. Zweck & Abgrenzung

Der Lernbereich ist ein **dritter Top-Level-Bereich** neben Dokumenten und Notizen. Er
überführt rohe Live-Mitschrift mit minimalem Aufwand in lernfähige Artefakte, die auf ihre
Quellen zurückzeigen. Er **referenziert und transformiert, besitzt aber keine Inhalte** –
die Wahrheit bleibt in Notiz und Dokument.

## 1. Getroffene Entscheidungen (steuern den Umfang)

| # | Entscheidung | Folge für den Umfang |
|---|---|---|
| E1 | **Kein Lern-Terminplan.** Browser-Modell: gelernt wird, wann der Nutzer will. | Kein Spaced-Repetition-Motor, keine Fälligkeiten/Intervalle, kein „heute fällig". Das `state`-Feld am Artefakt bleibt ein einfaches, offenes Feld (z. B. „zuletzt gelernt"), ohne Terminsteuerung. |
| E2 | **Startseite zeigt nur un-nachbereitete Sitzungen.** | Der sanfte Anstupser (Konzept §11.2) ist das einzige Lern-Element auf der PaperMind-Startseite. Die übrigen Rückstände leben **im** Lernbereich. |
| E3 | **Thema-Achse noch offen.** | Gruppierung nach Kurs/Sitzung/Typ/Status ist v1; die kursübergreifende „Thema"-Form (Tags vs. eigenes Objekt) ist eine offene Frage (§4). |

---

## 2. Funktionaler Leistungsumfang

Jede Anforderung ist als „das System muss …" zu lesen. Priorität in Klammern: **[v1]**
Kern, **[später]** Ausbaustufe.

### R1 · Verzahnung Notizen ↔ Lernraum **[v1]**
- Marker werden **in** der Notiz gesetzt, nie in einer Kopie.
- Ändert sich eine markierte Notizzeile, ändert sich die zugehörige Karte automatisch
  (eine Wahrheit; Fakten gehören der Notiz).
- Jede Karte kann auf ihre **Notizzeile und ihre Folie** zurückspringen (später Split-View).
- Die Notiz funktioniert ohne Lernraum unverändert weiter (der Lernraum liegt darüber).

### R2 · Eigener Bereich **[v1]**
- Der Lernbereich ist ein eigenständiger Bereich mit **eigener Startseite/Navigation**,
  kein Reiter der Notizen.
- Er bietet eine **Organisier-Fläche** (Leuchttisch-artig), auf der Kurse/Sitzungen/
  Lernblätter überblickt und angeordnet werden.

### R3 · Erfassung – die vier Eingänge **[v1]**
Der Pool muss über **alle vier** Wege befüllbar sein:
1. **Live-Marker** in der Mitschrift (eine Taste, generisch `lernen` oder typisiert).
2. **Nachträgliches Markieren** live durchgerutschter Zeilen (gleichwertig, kein Nebenfeature).
3. **PDF-Highlights** in Skript/Folien als Anker (Lese-Modus).
4. **Platzhalter-Anker** ohne PDF (Zeitstempel + Tippbeschreibung) mit späterem **Binden**
   an die echte Seite, sobald das PDF vorliegt.

### R4 · Objektstruktur **[v1]**
- Kurs → Sitzung → (Lernblatt) → Artefakt → Anker, plus Marker-Pool. Schemata:
  `lernbereich-datenmodell.md`. Genau **ein** Mitschrift-Dokument pro Sitzung; ein Kurs
  bündelt seine Foliensätze/Skripte.

### R5 · Betriebsart „Nachbereiten" (Review) **[v1]**
- Eine **Warteschlange** je Sitzung aus allen Markern **ohne** zugehöriges Artefakt.
- Abarbeitung **ein Marker nach dem anderen**, mit Fortschritt.
- Pro Marker: Typ bestätigen (vorbelegt mit Kurs-Default) → KI-Vorschlag prüfen →
  **Übernehmen / Anpassen / Verwerfen**.
- **Befüllung je Typ verschieden** (Rückseite aus: Notiz / Skript+Beleg / Mensch / Bild /
  bewusst leer). Nur der selbstgeschriebene Lösungsweg (Typ 6) ist echtes Tippen.

### R6 · Betriebsart „Lernen" **[v1]**
- **Kein Zeitplan** (E1): der Nutzer wählt ein Lernblatt und geht es durch.
- **Vier Abfrage-Muster** je Artefakttyp: aufdecken (Fakt) · aktiv wiederherstellen
  (Prozess/Vergleich) · frei formulieren + abgleichen (Verständnis) · selbst lösen +
  Lösung prüfen (Übung/Skizze). Typ 4 (Prozedural) ist „einmal durchspielen + abhaken".
- **Selbstbewertung** ist Rückmeldung/Markierung (z. B. „konnte ich / nicht"), steuert
  aber **keinen** Folgetermin (E1).
- Ein Lernblatt ist **gemischt** durchlaufbar; jede Karte hat den Rücksprung (R1).

### R7 · Betriebsart „Organisieren/Pflegen" **[v1]**
- Lernblätter zusammenstellen (pro Sitzung oder kursübergreifend), Artefakte gruppieren
  und ordnen, selbstgeschriebene Überblickssätze setzen (legitimer Eigen-Content).
- Lösungswege nachpflegen, Typen nachträglich ändern, Platzhalter-Anker binden.

### R8 · Sortier- und Gruppier-Achsen **[v1]**
- Gleichzeitig filter-/gruppierbar nach **Kurs, Sitzung, Typ/Modus, Herkunft, Status**.
- **Thema** (kursübergreifend) ist als Achse vorgesehen, aber in der Form **offen** (§4).

### R9 · Herkunft & Prüf-Workflow **[v1 Flag / später Liste]**
- Jedes Artefakt trägt dauerhaft ein **Herkunfts-Flag** („Skript S.9" / „extern, ungeprüft").
- Ein externes Artefakt hat einen **Prüf-Status** (ungeprüft → geprüft).
- Eine **Ansicht der ungeprüften externen Artefakte** (Abarbeitungsliste der riskantesten
  Lücken) lebt **im** Bereich, nicht auf der Startseite (E2). **[später]**

### R10 · KI als Vorschlag, nie Autopilot **[v1 Basis / später Skript-Retrieval]**
- KI kann: Aussage → Frage drehen, formatieren, mehrere Aussagen verdichten. **[v1]**
- KI antwortet **bewusst nicht** bei Verständnisfragen und rechnet Übungsaufgaben nicht.
- **Skript-gestützte Antworten** nur aus dem eigenen Skript mit **Seitenbeleg** (Retrieval);
  bei schweigendem Skript optional externe Antwort, klar als „extern/ungeprüft" markiert. **[später]**
- **Jede** KI-Ausgabe ist ein annehmbarer/verwerfbarer Vorschlag.

### R11 · Suchen & Wiederfinden **[später]**
- Artefakte und Lernblätter durchsuch- und filterbar über die Achsen aus R8; perspektivisch
  in die globale PaperMind-Suche eingebunden.

### R12 · Fortschritt & Abdeckung **[später]**
- „Wo stehe ich?" je Kurs/Sitzung: wie viel nachbereitet, wie viel gelernt, was schwach.
- Perspektivisch Klausurbezug („Klausur in X Tagen → das ist noch offen").

### R13 · Startseiten-Integration **[v1]**
- Die PaperMind-Startseite zeigt **un-nachbereitete Sitzungen** als sanften Anstupser
  (Konzept §11.2), gespeist aus der Warteschlangen-Query (R5). Keine weiteren Lern-Kacheln (E2).

### R14 · Robustheit & Lebenszyklus **[v1]**
- Stabile Anker (lazy `pmId`); verschwindet die Quelle, wird der Anker **verwaist**
  („Quelle fehlt"), das Artefakt bleibt – nie stiller Löschtod.
- Soft-Delete / Papierkorb analog Notizen; definiertes Verhalten bei **Kurs archivieren**
  und **Notiz löschen** (SET NULL, Verwaisung sichtbar).

### R15 · Skalierung & Modul-Profile **[später]**
- Tragfähig für viele Kurse/Sitzungen und hunderte Artefakte (Grund für R8).
- **Modul-Profile**: Default-Artefakttyp + Skript-Flag je realem Modul vorbelegt.

### R16 · Datenisolation **[v1]**
- Alle Objekte owner-scoped mit RLS, analog Migration 041. Reines Nutzerobjekt, kein
  Worker-/Systempfad.

---

## 3. Nicht-Ziele (ausdrücklich außerhalb des Umfangs)

- **Kein zweiter Inhaltsspeicher** – keine umformulierte Kopie von Fakten.
- **Kein KI-Autopilot** – die Kuratierung bleibt beim Menschen.
- **Keine Autokorrektur** für Rechen- oder Skizzieraufgaben – nur Selbstkontrolle.
- **Kein Spaced-Repetition-Terminplan** (E1).
- **Kein volles LMS** – keine Fremdkurse, kein Teilen/Export von Lernblättern (v1).
- **Kein Ersatz der Wissensbasis/Wiki.**

---

## 4. Offene Fragen

1. **Thema-Achse (E3):** PaperMind-Tags wiederverwenden vs. eigenes Thema-Objekt.
2. **Selbstbewertung:** Wird sie überhaupt persistiert (z. B. „zuletzt gelernt / konnte
   ich nicht"), obwohl es keinen Terminplan gibt – als leiser Anhalt beim nächsten Durchgang?
3. **PDF-Marker-Ablage:** Seitentabelle `learn_highlight_marker` vs. Spalte
   `annotations.learn_kind` (Datenmodell §3.5).
4. **Blatt↔Artefakt:** normalisierte n:m vs. JSONB (Datenmodell §3.9).
5. **Skript-Retrieval:** konkretes Verfahren, Seitenbeleg erzeugen (R10 / Datenmodell offen).
6. **Skizzieraufgaben:** minimaler Workflow für bildbasierte Musterlösung + Selbstabgleich.

---

## 5. Umfangs-Kern für v1 (Zusammenfassung)

Eigenständiger Bereich (R2) mit Objektstruktur (R4), vier Erfassungswegen (R3), den drei
Betriebsarten Nachbereiten/Lernen/Organisieren (R5–R7) im **Browser-Modell ohne Zeitplan**,
Sortierung/Gruppierung über die konkreten Achsen (R8), nahtloser Notiz-Verzahnung (R1),
Herkunfts-Flag (R9), KI-Vorschlägen als Basis (R10), Anker-Robustheit/Lebenszyklus (R14),
Startseiten-Anstupser für un-nachbereitete Sitzungen (R13) und Owner-Scoping (R16).
Alles Weitere ist Ausbaustufe.
