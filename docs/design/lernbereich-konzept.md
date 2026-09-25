# PaperMind – Lernbereich: Konzept

*Entwurf aus der Diskussion vom 10.09.2026. Grundlage: PaperMind als bestehende
Webanwendung für Dokumente (PDFs) und Notizen (Markdown). Ziel: ein dritter Bereich
„Lernen", der Mitschreiben im Online-Unterricht, leichte Nachbereitung und nachhaltiges
Lernen zusammenführt – validiert am Studiengang Medieninformatik (VFH), insbesondere am
Modul Computergrafik 1.*

---

## 1. Leitgedanke

Das eigentliche Problem eines Studenten-Notizsystems ist nicht der Editor, sondern der
**Bruch zwischen Mitschreiben und Lernen**. Die meisten Mitschriften werden nie in
lernfähiges Material überführt, weil die Nachbereitung als Neuschrieb empfunden wird und
deshalb ausbleibt.

Der gesamte Lernbereich verfolgt daher ein einziges übergeordnetes Ziel:

> **Nachbereitung soll als leichte Anreicherung der Mitschrift entstehen, nicht als
> Neuschrieb.** Aus roher Live-Mitschrift werden mit minimalem Aufwand lernfähige
> Artefakte, die auf ihre Quellen zurückzeigen.

Zwei Prinzipien halten das System langfristig konsistent:

1. **Der Inhaltstyp bestimmt das Lernartefakt, nicht umgekehrt.** Es gibt nicht „ein
   Lernformat für alles". Faktenwissen, Rechenaufgaben und Verständnisfragen verlangen
   verschiedene Artefakte.
2. **Der Lernbereich referenziert und transformiert, aber besitzt keine Inhalte.** Die
   Wahrheit über den Stoff liegt in Dokumenten und Notizen. Der Lernbereich hält
   Beziehungen, Struktur und Lernzustand – keine zweite, driftende Kopie der Inhalte.

---

## 2. Architektur: drei Bereiche

PaperMind trennt **Speicherung** von **Nutzungskontext**.

| Bereich | Rolle | Inhalt |
|---|---|---|
| **Dokumente** | Substanz-Ebene | PDFs (Foliensätze, Skripte). Textebene vorausgesetzt. |
| **Notizen** | Substanz-Ebene | Markdown. Eigene Mitschriften und Texte. |
| **Lernen** | Sicht- & Verknüpfungsebene | Beziehungen, Marker, Artefakte, Lernzustand. Kaum eigener Inhalt. |

Der Lernbereich legt sich **über** die beiden Substanz-Ebenen. Dieselbe Notiz kann
gleichzeitig Referenzmaterial und Lernobjekt sein, ohne dupliziert zu werden.

> **Hinweis (Code-Prüfung 21.09.2026):** Notizen liegen in PaperMind nicht als Markdown,
> sondern als **TipTap/ProseMirror-JSON** (`note.body_json`) vor. Die Marker (§4) werden
> daher eigene Node-Attribute im JSON, keine Markdown-Zeilen. Details:
> `lernbereich-datenmodell.md`.

### 2.1 Die Regel gegen die dritte Substanz-Ebene

Die größte Gefahr: dass „Lernen" heimlich anfängt, eigene Inhalte zu speichern
(umformulierte Aussagen, Definitionen, Erklärungen). Sobald das passiert, gibt es zwei
Wahrheitsquellen, die auseinanderdriften – und das Neuschrieb-Problem ist zurück.

**Saubere Regel:**
- **Fakten und Aussagen** gehören der Notiz. Ein Lernartefakt zeigt auf eine markierte
  Notizzeile; wird die Aussage geändert, wird die Notiz geändert.
- **Ordnung und Verknüpfung** (Gruppierung, Reihenfolge, ein selbstgeschriebener
  Überblickssatz, der mehrere Aussagen verbindet) dürfen im Lernbereich leben. Das ist
  legitim eigener Lern-Content.

---

## 3. Objektmodell im Lernbereich

Drei Objekttypen, die selbst kaum Inhalt speichern, sondern Beziehungen und Zustand:

### Kurs
Container pro Modul (z. B. „Computergrafik 1"). Bündelt Sitzungen und die zugehörigen
Foliensätze/Skripte (Verweise auf PDFs im Dokumentenbereich).
Trägt außerdem den **Default-Artefakttyp** (siehe §5.3) und ein Flag, ob ein brauchbares
Skript vorliegt (siehe §7.4).

### Sitzung
Eine Vorlesung/ein Termin. Verweist auf **genau ein Mitschrift-Dokument** (Markdown im
Notizbereich) und auf **einen oder mehrere Foliensätze**. Hier leben die Anker (§4) und
die Platzhalter für den Fall „nur geteilter Bildschirm".

### Lernblatt
Die aus markierten Inhalten verdichtete, lernbare Sicht. Kann pro Sitzung oder
themenübergreifend über mehrere Sitzungen eines Kurses entstehen. Enthält die Artefakte
(§5) als Referenzen, plus die reine Lern-Struktur (Reihenfolge, Gruppierung).

---

## 4. Zwei Anker-Typen

Lerninhalte haben zwei verschiedene Herkünfte, die technisch nicht vermischt werden dürfen:

1. **Struktur-Marker in der eigenen Notiz** – eine Markdown-Zeile/ein Block wird als
   lernrelevant ausgezeichnet (`[fakt]`, `[warum]`, `[aufgabe]` …). Anker = Zeilen-/
   Blockreferenz im Markdown.
2. **Text-Highlight in einem fremden Dokument** – eine Textstelle in einem PDF (Skript,
   Foliensatz) wird hervorgehoben. Anker = Text-Range auf einer PDF-Seite.

Beide münden in denselben Lern-Pool, behalten aber ihre Herkunft. Zusätzlich:

- **Folienanker** (`@S12`, `@LE5`): verbindet eine Notizzeile mit einer konkreten
  Folie/Seite. Ermöglicht später Split-View (Folie links, Notiz rechts) und Rücksprung
  von der Notiz zur Quelle.
- **Platzhalter-Anker** für den Fall, dass live kein PDF vorliegt (nur geteilter
  Bildschirm): Zeitstempel + kurze Tippbeschreibung. Wird nachträglich an echte
  Seiten gebunden, sobald das PDF verfügbar ist. Billiger, bewusster Nachbereitungsschritt.

---

## 5. Die Artefakttypen

Der Stresstest an echten Modulen hat gezeigt: Ein Ein-Typ-System (alles wird eine
Karteikarte) scheitert. Nötig sind **sechs Typen**. Die Zuordnung orientiert sich an der
Bloom-Taxonomie, die das Modulhandbuch pro Modul ohnehin ausweist.

### 5.1 Übersicht

| # | Typ | Bloom-Stufe | Lernartefakt | KI-Eignung |
|---|---|---|---|---|
| 1 | Fakt / Definition | Wissen | Frage→Antwort-Karte (Abruf) | **hoch** – KI dreht Aussage zu Frage |
| 2 | Prozess / Ablauf | Wissen/Verstehen | Sequenzkarte (Reihenfolge prüfen) | mittel |
| 3 | Zusammenhang / Vergleich | Analysieren | Vergleichstabelle / Übersicht | mittel |
| 4 | Prozedurales / Anwendung | Anwenden | Verlinkte Anleitung + einmal durchspielen | gering |
| 5 | Verständnis / Begründung | Verstehen/Evaluieren | Offene Frage, frei formuliert | **bewusst keine** KI-Antwort |
| 6 | Übungsaufgabe (überprüfbar) | Anwenden | Aufgabe + Lösungsweg, Selbstkontrolle | **gering** – Handarbeit |

### 5.2 Erläuterung der kritischen Typen

**Typ 5 (Verständnis):** Hier generiert die KI *bewusst nicht* die Antwort. Sonst lernt
man, die eigene Notiz zu erinnern, statt zu verstehen. Das Artefakt ist nur die Frage; die
Antwort formuliert man frei und deckt dann die Notiz als Abgleich auf.

**Typ 6 (Übungsaufgabe):** Der Typ, der im rein notizbasierten Kartenmodell fehlte. Für
Mathe, SQL, Programmierung, Computergrafik-Transformationen. Eine Karte „Wie multipliziert
man Matrizen?" ist wertlos – man muss *rechnen*. Lösung + Rechenweg auf der Rückseite,
Selbstkontrolle. **KI ist hier nur Formatierungshilfe, nicht Lösungsquelle** (siehe §7.3).

**Grenzfall Skizzieraufgabe:** In Modulen wie Computergrafik gibt es Konstruktions-/
Skizzieraufgaben, deren Lösung eine Zeichnung ist. Ein textbasiertes Markdown-System kann
das nicht autokorrigieren. Pragmatische Lösung: Aufgabe mit hinterlegter Musterskizze
(Bild/Foto), Selbstkontrolle statt Autokorrektur. **Diese Grenze ist bewusst zu kennen.**

### 5.3 Klassifikation: wo und wann

Die Zuordnung ist **nicht** auf Modul- oder Kapitelebene stabil – innerhalb eines einzigen
Kapitels wechselt sie (Beispiel Kap. 4 Computergrafik in §8 enthält alle vier Kerntypen).
Deshalb:

- **Default-Typ pro Kurs** als Vorbelegung (z. B. Computergrafik → „Aufgabe",
  Selbstmanagement → „offene Frage"). Spart Tipparbeit.
- **Endgültige Klassifikation auf Ebene der einzelnen markierten Aussage.**
- **Live nur ein generischer Marker** (`[lernen]`) ist erlaubt; der genaue Typ wird in der
  Nachbereitung verfeinert. Vier Typen live sauber zu trennen erzeugt zu viel kognitive
  Last und sabotiert das Zuhören. Der Kurs-Default fängt Unklassifiziertes ab.

---

## 6. Editor-Verhalten

### 6.1 Live-Modus (Mitschreiben)

Annahme: Tippen am Laptop, parallel zum Zuhören. Der Editor darf **keine** kognitive Last
erzeugen.

- Reines Markdown, kein Formatieren mit der Maus.
- **Ein** Tastenkürzel setzt einen Lern-Marker auf die aktuelle Zeile (generisch oder,
  wenn schnell genug, typisiert).
- **Ein** Tastenkürzel setzt den Folienanker (`@S12`).
- Keine strukturellen Entscheidungen während des Unterrichts. Chronologisch, roh.

### 6.2 Lese-Modus (fremde Dokumente)

- Textstellen in PDFs (Skript/Folien) hervorheben → Text-Range-Highlight (Anker-Typ 2).
- Highlights sind Rohmaterial für Artefakte, nicht selbst schon Karten.

### 6.3 Nachbereitung

Kein Neuschrieb, sondern Durchgehen der Marker (ca. 10 Min pro Sitzung):
- Marker sichten, Typ verfeinern.
- KI-Vorschläge pro Marker prüfen und annehmen/verwerfen (§7).
- Live durchgerutschte, aber wichtige Zeilen **nachträglich** markieren. (Nachträgliches
  Markieren ist kein Nebenfeature – es fängt genau das prüfungsrelevante Zeug ein, das
  live keinen Marker bekam.)

> Ort und Auslöser dieser Nachbereitung sind in **§11** konkretisiert (Review-Bildschirm
> + sanfter Anstupser).

---

## 7. KI-Rollenverteilung

Grundsatz: **Der Mensch entscheidet, *was* gelernt wird. Die KI erledigt die
Transformation – *wie* etwas zur Frage/zum Artefakt wird.** Die Kuratierung bleibt beim
Menschen, denn sie ist es, die Lernen wirksam macht.

### 7.1 Was die KI zuverlässig kann
- Aus einer `[fakt]`-Aussage eine Frage→Antwort-Karte drehen.
- Artefakte formatieren, Aufgabenstellungen sauber aufbereiten.
- Aus mehreren markierten Aussagen eine Übersicht/Vergleichstabelle verdichten.

### 7.2 Was die KI bewusst *nicht* tut
- Antworten auf Verständnisfragen (Typ 5) vorwegnehmen.
- Die Kuratierung übernehmen („mach mal alles automatisch").

### 7.3 Wo die KI nur Hilfskraft ist
Übungsaufgaben (Typ 6). KI kann die Methode aus dem Skript zusammensuchen, aber rechnet
konkrete Aufgaben oft plausibel-falsch (Vorzeichen bei sin/cos, Drehrichtung). **Die Lösung
liefert oder prüft der Mensch.** Blindes Vertrauen bedeutet, einen Fehler zu lernen.

### 7.4 Skript-gestützte Nachbereitung (Antworten auf Verpasstes)

Ziel: Fragen beantworten, die live nicht mitgeschrieben werden konnten – **aus dem
eigenen Skript**, nicht aus dem Weltwissen der KI.

**Zwei Fälle streng trennen:**

- **Fall A – Antwort aus dem Skript.** Die KI bekommt den Skript-Text als Kontext und die
  Anweisung, *nur daraus* zu antworten und die Fundstelle zu belegen (Seite/Abschnitt).
  Die markierte Live-Zeile wird zur Frage, die Skript-Passage zur Quelle, die KI-Antwort
  zum Vorschlag für die Artefakt-Rückseite – mit Seitenverweis. **Dies ist das erwünschte
  Verhalten.**
- **Fall B – allgemeine Erklärung aus KI-Wissen.** Bequem, aber riskant: kann von der
  Darstellung des Dozenten abweichen, andere Notation nutzen, in der Klausur nicht zählen.

**Regel:** Fall A ist Standard. Wenn das Skript schweigt oder fehlt, **darf** die KI eine
allgemeine Erklärung liefern (Entscheidung: Variante b), aber:
1. klar als **extern / ungeprüft** gekennzeichnet;
2. mit **Verweis auf die Modul-Literatur** zur Verifikation (bei Computergrafik z. B.
   Nischwitz/Fischer/Haberäcker, Brill/Bender – Literaturliste steht im Modulhandbuch).
   So wird die externe Antwort nicht Endpunkt, sondern Absprung zur Absicherung.

**Skript-Qualität steuert die KI-Unterstützung.** Sauber getextetes Skript = gute Quelle
für Fall A. Abfotografierte Folien ohne Textebene oder reine Stichpunkte = zu wenig Kontext,
KI rutscht Richtung Fall B. Deshalb das Skript-Flag pro Kurs (§3): Für Module ohne echtes
Skript werden Fall-A-Antworten gar nicht erst versprochen.

**Grenze:** Auch skript-gestützt hilft die KI bei Rechenaufgaben (Typ 6) nur begrenzt –
sie findet die Methode, rechnet die konkrete Aufgabe aber nicht zuverlässig fehlerfrei.

---

## 8. Herkunfts- und Prüfmodell (die Sicherung für Variante b)

Variante b (KI darf bei schweigendem Skript extern erklären) ist nur tragfähig mit zwei
Sicherungen, die verhindern, dass ungeprüftes Wissen als Dozentenstoff missverstanden wird.

### 8.1 Herkunft klebt am Artefakt, nicht an der Antwort
Ein Herkunfts-Flag **pro Artefakt**, das auch beim Lernen in drei Wochen sichtbar bleibt:
- `quelle: skript S.9` – belegt aus eigenem Material.
- `quelle: extern, ungeprüft` – aus KI-Wissen, noch nicht abgeglichen.

Ohne dieses dauerhafte Flag verwandelt sich ehrliche Unsicherheit unbemerkt in scheinbare
Gewissheit: Man erinnert den Inhalt, aber nicht seine Herkunft.

### 8.2 Prüf-Status für externe Artefakte
Ein externes Artefakt ist zunächst ein *Verdacht*. Zustand: „noch nicht gegen Dozentenstoff
abgeglichen". Nach Bestätigung (Präsenz, Forum, Skript, Literatur) → „geprüft".

Das ist kein Overhead, sondern eine **To-do-Liste der riskantesten Wissenslücken** –
genau die Fragen, die das Skript nicht beantworten konnte, sind die mit dem höchsten
Fehler-Risiko. Der Status macht sie sichtbar, statt sie im Kartenstapel verschwinden zu
lassen.

---

## 9. Durchgespieltes Referenzbeispiel: Computergrafik 1, Kap. 4 (2D-Transformationen)

Härtester Testfall, weil hier alle Kerntypen in einem Kapitel auftreten. Klausurform:
120 Min, prüft Rechnen/Konstruieren – nicht Faktenwissen. Wer Definitionen paukt, fällt
durch.

### 9.1 Phase 1 – Live-Mitschrift (roh)

```markdown
## 2D-Transformationen  @LE5

Translation verschiebt Punkt um Vektor. @S4
- P' = P + t

[fakt] Skalierung: Streckung/Stauchung um Faktor sx, sy @S6
[warum] Warum reicht Translation nicht als Matrixmultiplikation? @S8
  -> Verschiebung ist Addition, keine lineare Abb.
[fakt] homogene Koordinaten: (x,y) -> (x,y,1) @S9
[warum] Dadurch wird Translation zu Matrixmult. -- Kernidee der ganzen LE @S9

Rotation um Ursprung, Winkel theta @S11
[aufgabe] Rotationsmatrix aufstellen + Punkt (2,0) um 90° drehen @S12

[analyse] gegebene Matrix zerlegen: welche Abbildungen? @S15
Reihenfolge!! Rotation dann Translation != Translation dann Rotation @S16
[aufgabe] zusammengesetzte Abb: erst skalieren, dann rotieren @S17
```

Beobachtung: minimale Live-Entscheidung (ein Marker + Folienanker pro Zeile). Die Zeile
„Reihenfolge!!" hat *keinen* Marker – wird live nicht klassifiziert. Das ist realistisch.

### 9.2 Phase 2 – Nachbereitung

- **`[fakt]` homogene Koordinaten** → KI dreht zu Karte: *V:* „Wie werden kartesische 2D-
  Koordinaten in homogene überführt?" *R:* „(x,y) → (x,y,1)". Zeigt auf Notizzeile + @S9.
  Funktioniert gut.
- **`[warum]` Translation → Matrixmult.** → offene Verständnisfrage, KI liefert **keine**
  Antwort. Beim Lernen frei formulieren, dann Notiz aufdecken.
- **`[aufgabe]` Rotation (2,0) um 90°** → Aufgaben-Artefakt. KI formatiert; **Lösung
  ((0,2), Vorzeichen sin/cos, Drehrichtung) prüft/liefert der Mensch.** Ehrlicher Bruch:
  KI rechnet hier plausibel-falsch.
- **`[analyse]` Matrix zerlegen** → offene Analyseaufgabe mit Beispielmatrix, Lösung
  vom Menschen kontrolliert.
- **Nicht markierte Zeile „Reihenfolge!!"** → in der Nachbereitung als das
  prüfungsrelevanteste Konzept erkannt (Nicht-Kommutativität). Jetzt nachträglich markiert
  als `[warum]` + `[aufgabe]` („Zeige an einem Beispiel, dass RT ≠ TR").

### 9.3 Phase 3 – Lernen

Gemischtes Lernblatt, Modus je Typ unterschiedlich:
- Faktenkarten: verdecken → erinnern → aufdecken (Abruf-Rhythmus).
- Verständnisfragen: frei formulieren vor dem Aufdecken.
- Aufgaben: auf Papier rechnen, dann Selbstkontrolle gegen gepflegte Lösung.
- Jedes Artefakt: Rücksprung auf Notizzeile + Folie, falls man hängt.

### 9.4 Was der Durchlauf beweist
1. Die Kette Mitschrift → Marker → KI-Vorschlag → Prüfen → Artefakt **trägt**; die
   Nachbereitung bleibt leicht (anreichern statt neu schreiben).
2. Der Anteil, den KI **verlässlich** übernimmt, ist bei rechenlastigen Modulen klein
   (im Wesentlichen Faktenkarten + Formatierung). Für Computergrafik ist das System eher
   ein **Aufgaben-Verwalter mit Selbstkontrolle** als ein KI-Kartengenerator.
3. Der Live-Marker muss **optional verfeinerbar** sein, nicht live-verpflichtend.

---

## 10. Offene Punkte / nächste Schritte

- **Datenmodell technisch ausformulieren:** konkrete Schemata für Kurs, Sitzung,
  Lernblatt, Artefakt (inkl. Herkunfts-Flag, Prüf-Status, Anker-Referenzen).
  → **erledigt:** `lernbereich-datenmodell.md`.
- **Marker-Syntax festlegen:** finales Set der Inline-Marker und Folienanker; wie wird
  ein generischer `[lernen]`-Marker gespeichert und später typisiert.
- **Anker-Robustheit:** Wie überstehen Zeilen-/Block-Anker spätere Edits der Notiz?
  (Stabile IDs statt Zeilennummern.) → **gelöst im Datenmodell** (lazy `pmId` auf
  markierbaren Nodes).
- **Skript-Bindung technisch:** Wie wird die relevante Skript-Passage für eine Frage
  gefunden (Retrieval), und wie wird der Seitenbeleg erzeugt?
- **Modul-Profile:** Default-Artefakttyp und Skript-Flag für die realen Module des
  Studiengangs vorbelegen (Referenztabelle über alle Module).
- **Skizzieraufgaben:** minimaler Workflow für bildbasierte Musterlösung + Selbstabgleich.

---

## 11. Nachbereitung: Ort und Auslöser (Entscheidung 21.09.2026)

Ergänzung aus der Design-Sitzung. Legt fest, **wo** die Nachbereitung (§6.3)
stattfindet und **wie** der Nutzer dorthin findet. Verwandtes technisches Modell:
`lernbereich-datenmodell.md`.

### 11.1 Ein eigener Review-Bildschirm, kein Neuschrieb im Editor

Zwei Tätigkeiten werden strikt getrennt:

- **Marker *setzen*** passiert **live im Notiz-Editor** – eine Taste, während des
  Zuhörens (§6.1).
- **Marker *veredeln*** passiert **danach in einer Nachbereitungs-Ansicht** der Sitzung,
  einem eigenen Bildschirm im Lernbereich.

Die Ansicht ist ein **Review, kein leeres Formular**:

- **Warteschlange:** Alle markierten Zeilen *ohne* zugehöriges Artefakt bilden die
  Schlange (dieselbe Rechnung wie im Datenmodell: Marker ohne `source`-Anker). Abgearbeitet
  wird **ein Marker nach dem anderen**, mit Fortschritt („3 von 6 · ~5 Min übrig").
- **Zwei Spalten:** links die markierte Zeile **im Kontext der eigenen Notiz** (damit klar
  ist, worum es ging), rechts der **fertige KI-Vorschlag**, der zur Karte wird.
- **Immer dieselbe kleine Schleife pro Marker:** (1) Typ bestätigen – vorbelegt mit dem
  Kurs-Default (§5.3), per Chip änderbar; (2) Vorschlag prüfen – Vorder- und (wo erlaubt)
  Rückseite sind schon befüllt; (3) **Übernehmen / Anpassen / Verwerfen** → nächster Marker.
- **Die rechte Seite verhält sich je Typ anders** (§5, „Befüllen"): Fakt hat die Rückseite
  schon (Quelle: Notiz), Verständnis lässt sie leer, Aufgabe zeigt ein leeres Feld für den
  selbst geschriebenen Lösungsweg.

Ist die Schlange leer, ist die Sitzung nachbereitet – das sind die angepeilten ~10 Minuten.

**Woher der Inhalt kommt (Befüllung).** Die Vorderseite ist fast immer eine KI-Transformation
der markierten Zeile. Die Rückseite stammt aus einer von fünf Quellen, je Typ verschieden:
(1) der Notiz selbst = kein Tippen (Fakt); (2) dem eigenen Skript mit Seitenbeleg (§7.4
Fall A); (3) dem Menschen = echter Eigen-Content (Lösungsweg Typ 6); (4) einem hinterlegten
Bild (Skizze); (5) bewusst leer (Verständnis, Typ 5). Nur bei Quelle 3 wird wirklich getippt.

### 11.2 Auslöser: Variante B – der sanfte Anstupser

Das Konzept steht und fällt damit, dass die Nachbereitung *tatsächlich passiert* (§1).
Statt sie allein vom aktiven Öffnen der Sitzung abhängig zu machen (Variante A), wird der
Nutzer **hingezogen** – bewusst sanft, nicht als nörgelnde To-do-Glocke.

**Andockpunkt (kein neuer Mechanismus):** die bestehende PaperMind-Übersicht mit ihren
owner-scoped Attention-Kacheln (`/api/dashboard/overview`). Es kommt **eine Kachel-Art**
dazu, deren Zahl dieselbe Abfrage ist wie die Warteschlange – „Marker ohne Karte", nach
Sitzung gruppiert. Zusätzlich zeigt die Sitzungsliste im Lernbereich denselben Zustand als
leises Abzeichen.

**Die Regeln, die den Nudge sanft halten:**

1. **Ruhige Farbe, keine Alarm-Signale.** Grün/neutral statt Rot; keine rote Zähler-Blase.
2. **Zeitangabe senkt die Hürde.** „~10 Minuten" sagt: kein Berg.
3. **„Solange es frisch ist" statt „überfällig".** Einladender Ton, keine Beschämung;
   „Später" ist ein gleichwertiger Knopf.
4. **Sie verschwindet von allein**, sobald die Warteschlange leer ist.
5. **Ältere Sitzungen eskalieren nicht** – sie rutschen in eine leise Nebenzeile, statt zu
   einem Stapel roter Badges zu werden.

**Warum B statt A:** A (nur aktives Öffnen) ist sauber getrennt, bleibt aber liegen. B zieht
sanft hinein und respektiert zugleich, dass Nachbereitung am wirksamsten ist, solange der
Stoff frisch ist.
