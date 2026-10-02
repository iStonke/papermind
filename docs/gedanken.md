# Gedanken im Notizbereich

Umsetzung der Phase 1 aus Projekt-Memory `notes-pinnwand-konzept`, mit dem entschiedenen Namen **Gedanken**. Die spätere Nutzerentscheidung für freie Positionierung ersetzt die ursprüngliche Masonry-Vorgabe.

- Eigener Eintrag ganz oben unter Notizen, auch in der kompakten Seitenleiste; Zähler zeigt offene Gedanken der aktiven Sammlung.
- Zweigeteilte Ansicht: links Suche, Tagesgruppen und Mehrfachauswahl; rechts direkte Plain-Text-Erfassung und eine freie, scrollbare Fläche mit dauerhaft gespeicherten Kartenpositionen.
- Neue, inhaltslose Karten werden bei einem Klick außerhalb automatisch geschlossen; Entwürfe mit Text bleiben erhalten.
- Die Titelzeile ist dauerhaft als abgesetzte Leiste sichtbar und enthält das Datum; sie dient weiterhin zum Verschieben.
- Bedienelemente auf Karten erscheinen erst beim Hover oder Tastaturfokus; auf Touch-Geräten beim Fokus nach Antippen.
- Kein Titel, Notizbuch oder Rich-Text-Editor. Ein Doppelklick auf eine freie Stelle lässt dort mit einer kurzen Wachstumsanimation eine neue Karte entstehen und setzt die Schreibmarke; ein einfacher Canvas-Klick hebt Auswahl und Markierung auf. Neue Karten werden an den sichtbaren Ausschnitt angepasst und bleiben vollständig darin; bestehende Texte lassen sich durch Anklicken direkt bearbeiten. Festhalten per Schaltfläche oder ⌘/Strg+Enter, Zeilenumbrüche bleiben erhalten.
- Die Titelleistenfarbe ist pro Gedanke über eine beim Hover sichtbare Farbauswahl anpassbar, auch während der Erfassung. Hex-Farben werden serverseitig validiert und gespeichert (Migration `104_note_pin_color`); Datum und X erhalten eine kontrastreiche Schriftfarbe.
- Direktes Bearbeiten ohne Speichern-/Abbrechen-Buttons und ohne Größensprung: Textfelder übernehmen die Texthöhe und wachsen mit weiteren Zeilen. Bestehende Gedanken speichern nach 600 ms Schreibpause sowie beim Verlassen; neue Gedanken werden beim Verlassen erfasst. Speicherfehler bleiben sichtbar, der lokale Entwurf bleibt erhalten.
- Eingabeentwürfe und Bearbeitungsentwürfe werden lokal pro Benutzer und Sammlung gesichert. Karten können direkt bearbeitet und an der Titelleiste frei verschoben werden (auch per Pfeiltasten); konkurrierende Änderungen werden anhand `updated_at` erkannt.
- `#Hashtags` verwenden das gemeinsame Tag-Vokabular. Beim Bearbeiten werden die Tags aus dem neuen Text abgeleitet; der Text selbst bleibt unverändert.
- Das X oben rechts entfernt einen Gedanken von der Fläche (wiederherstellbar im Archiv); ein Archivieren-Button auf der Karte entfällt. Einzelne und ausgewählte Gedanken können archiviert, rückgängig gemacht und aus dem Archiv zurückgeholt werden. Keine automatische Löschung.
- Beim Löschen einer Sammlung werden auch ihre Gedanken in die gewählte Zielsammlung verschoben.

## Datenhaltung und API

Migration `102_note_pin` erstellt `note_pin` und `note_pin_tags` mit Owner-Isolation (RLS). Migration `103_note_pin_position` ergänzt die freien X/Y-Positionen. Gedanken sind eigenständige Objekte und verändern weder Notizlisten noch Notizzähler. Sammlungen sind Pflicht; Text ist auf 20.000 Zeichen begrenzt.

API unter `/api/notes/pins`: Liste, offener Zähler, Anlage, Bearbeitung, Positionsänderung und Sammelarchivierung. Jede Operation validiert Besitzer und Sammlung. Statuswerte `open`, `sorted`, `archived`; `sorted` ist für Phase 2 reserviert.

## Spätere Phasen

Phase 2: KI-Sortieren über einen dedizierten Endpunkt, überprüfbare Stapelvorschläge mit Annehmen/Ablehnen, unveränderte Originaltexte, Rückgängig und Drag von Liste zu Stapel.

Phase 3: zusätzliche Erfassungseinstiege über ⌘K, Kürzel, Popover, Anstupser und Mobile Share-Target.

## Prüfung

17 Backend-Integrationstests (Gedanken und Sammlungen) erfolgreich; Frontend-Build inklusive Bundle-Budget erfolgreich. Browserprüfung auf Vite `127.0.0.1:5179` mit temporärem Konto: Erfassung, Tastatur, Bearbeitung, Sammlungswechsel, Entwurfsicherung, Mehrfachauswahl, Archiv und Rückgängig. Freie Klickposition, Wachstumsanimation, Verschieben und Wiederherstellung nach Neuladen wurden ebenfalls im Browser geprüft.

Frontend-Suite: 595 von 601 Tests erfolgreich; sechs bestehende Fehler in `headerIconButtonStyle`, `lernraumNavigation` und `notesWorkspaceLayout`. Dieselben sechs Fehler wurden am unveränderten Git-HEAD reproduziert.

Die Gedankenliste verwendet die gemeinsamen Dokumentkarten-Stile mit Vorschau, Titel, Tags und Datum sowie einer kompakten Suche im Kopf. Tagesgruppen, Checkboxen, Archivzugang, Filterleiste und Verwaltungsbereich entfallen.

## Gedankensammlungen

Die Liste zeigt Gedankensammlungen statt einzelner Gedanken. Der Listenbutton „Neue Sammlung“ legt ohne Namensdialog eine Sammlung mit einem automatischen Namen wie „Sammlung 1“ an; über das Stiftsymbol lässt sie sich umbenennen. Die bisherige Bezeichnung „Fläche“ entfällt für diesen Bereich. Suche und Sortierung beziehen sich auf die Gedankensammlungen. Jede enthält eigene Gedanken und Positionen; Toolbarbutton und Doppelklick erstellen Gedanken in der aktiven Gedankensammlung. Technisch bleiben die bisherigen Räume (`thought_room`) und ihre Zuordnung zu den übergeordneten Notizsammlungen bestehen. Entwürfe sind nach Benutzer, Notizsammlung und Raum getrennt gespeichert. Migration `105_thought_rooms` überführt bestehende Gedanken einschließlich archivierter Einträge in „Meine Gedanken“. Die automatische Nummerierung berücksichtigt auch vorhandene Namen „Fläche N“.

Mehrfachauswahl: Auf der freien Fläche klicken, halten und einen Auswahlrahmen ziehen. Shift/Strg/⌘ erweitert die Auswahl; ein Klick auf die freie Fläche hebt sie auf. Die Farbpalette in der Toolbar färbt alle ausgewählten Gedanken mit einer atomaren API-Änderung und Konfliktprüfung. Der rote Löschen-Button entfernt die Auswahl wiederherstellbar, „Rückgängig“ stellt sie zurück. Keine Checkboxen auf Karten.

Ausgewählte Gedanken lassen sich gemeinsam an einer ihrer Titelleisten verschieben, auch per Pfeiltasten. Die Gruppe erhält ein gemeinsames Delta und bewahrt ihre Abstände an den Canvas-Grenzen. Alle Positionen werden in einer atomaren API-Änderung mit Besitzer- und Versionsprüfung gespeichert; bei Fehlern wird die gesamte Gruppe zurückgesetzt.

## KI-Zusammenfassung als neue Notiz

Der KI-Button „Alle Gedanken zusammenfassen“ in der Canvas-Toolbar verarbeitet alle offenen Gedanken der aktiven Gedankensammlung, unabhängig von der Auswahl. Laufende Textbearbeitungen werden zuvor gespeichert. Die KI führt Wiederholungen zusammen, erhält Aufgaben und offene Fragen und ergänzt sinnvolle Zusammenhänge. Zusätzliche Ideen sind als Vorschläge, unsichere Schlüsse als Annahmen zu kennzeichnen.

1. `POST /api/notes/pins/rooms/{room_id}/summary` erzeugt ausschließlich eine Vorschau aus Titel und Markdown-Inhalt. Ein kompakter Dialog zeigt beides editierbar. Schließen oder „Zurück“ legt keine Notiz an.
2. Erst „Als Notiz übernehmen“ erzeugt über die bestehende Notiz-API eine normale Notiz in derselben Sammlung mit dem bearbeiteten Titel und Inhalt und öffnet sie in „Alle Notizen“. Die ursprünglichen Gedanken bleiben erhalten.

Der Endpunkt prüft Besitzer und Gedankensammlung und verwendet die konfigurierte Textgenerierung einschließlich vorhandener Anbieter-Fallbacks. Größere Gedankensammlungen werden vollständig in Teilzusammenfassungen verarbeitet statt abgeschnitten. Ungültige, leere oder unvollständige KI-Antworten werden mit einer wiederholbaren Fehlermeldung abgewiesen. Die Vorschau verändert keine Datenbankeinträge.

Prüfung der Erweiterung: Backend-Tests für Besitzerschutz, leere Gedankensammlung, vollständige Verarbeitung großer Eingaben und ungültige/abgebrochene Antworten; Browser-Tests für Abbrechen ohne Notizanlage und Übernahme des editierten Titels und Inhalts mit Öffnung der neuen Notiz. KI-Antworten sind in diesen Tests simuliert.

## Hell- und Dunkelmodus

Gedanken verwenden die gemeinsamen Theme-Tokens für Text, Nebeninformationen, Akzent, Schatten und Fehler. Im Dunkelmodus hebt sich die Kartenfläche durch den erhöhten Oberflächenfarbton vom Canvas ab; eigene Titelleistenfarben behalten ihre passende Kontrastschrift. Die in den Dokumentkörper ausgelagerte Farbpalette erhält eine reaktive Theme-Wurzel und wechselt auch im geöffneten Zustand mit dem Theme. Browserprüfungen messen mindestens 4,5:1 Textkontrast für alle sieben Titelleistenfarben, den Standardfarbton und die Listeninformationen und prüfen Bearbeitung, Entwurf, Auswahl, Farbpalette und Zusammenfassungsdialog bei Theme-Wechseln.

## Schnellerfassung über ⌘K

Die Command-Palette erfasst Gedanken ohne Navigation: Präfix `+` (zum Beispiel `+ Angebot Müller prüfen`) oder die Aktion „Gedanke festhalten …“ (füllt `+ `). Enter speichert den Text in der aktiven Notiz-Sammlung, die Zielfläche bestimmt die Einstellung „Schnellerfassung von Gedanken“ (Einstellungen → Notizen → Allgemein, `ui.notes_thought_capture_target`): **Neue Sammlung pro Tag** (der erste Gedanke des Tages legt eine Fläche „Gedanken TT.MM.JJJJ“ an, alle weiteren desselben Tages landen darin; wird sie umbenannt, entsteht für den Tag eine neue) oder **Zuletzt ausgewählte Sammlung** (Standard; die im Gedanken-Arbeitsbereich zuletzt gewählte Fläche, sonst die erste). Die Palette bleibt mit leerem Feld für den nächsten Gedanken offen und bestätigt kurz („Festgehalten“). Bei einem Fehler bleibt der Text stehen; Enter wiederholt mit derselben `request_id`, es entsteht kein Duplikat. Ist der Gedanken-Arbeitsbereich geöffnet, lädt er danach nach (`thoughtRevision` im Notizen-Store), sofern gerade nichts bearbeitet wird.

Ohne Positionsangabe wählt das Backend einen freien Platz auf einem 4-Spalten-Raster der Fläche, damit Schnellgedanken sich nicht stapeln. `position_x` und `position_y` gelten nur gemeinsam. Die Erfassung ist einzeilig; Zeilenumbrüche gibt es weiterhin nur in der Fläche.

`ensure_room` sperrt die Sammlung beim ersten Anlegen, sodass parallele Erstaufrufe nur eine Fläche „Meine Gedanken“ erzeugen.
