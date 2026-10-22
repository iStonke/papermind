# Technische Verbesserungen des Importfensters

Stand: 21. Oktober 2026. Die zuletzt vereinbarten UI-Entscheidungen bleiben erhalten; Mehrfachauswahl und Umsortieren wurden nicht neu gestaltet.

| Nr. | Änderung | Umsetzung |
| --- | --- | --- |
| 1 | Analyse von Darstellung trennen | `analysisRevision` berücksichtigt Quelle, Quellversion, Seiten, Reihenfolge und Drehung. Farbänderungen ändern ausschließlich die Darstellung. Analyseanfragen verwenden immer den vorbereiteten Quellmodus. |
| 2 | Vorschauen nach Quellversion invalidieren | Gemeinsame Seitenrevision für Miniatur-Nachladeaufträge und große Bilder. Auch inaktive Bilder werden ungültig. Nur das bereits sichtbare aktive Bild darf bis zum vollständig dekodierten Ersatz stehen bleiben; es wird nicht als Ergebnis der neuen Revision wiederverwendet. |
| 3 | Große Dokumente begrenzen | Alle Seiten behalten feste geometrische Plätze. Bilder werden nur in einem Fenster um die Auswahl beziehungsweise den sichtbaren Ausschnitt gemountet. Native Scrollposition und Einrastpunkte bleiben erhalten. |
| 4 | Bildcache nach Speichergröße begrenzen | LRU mit 48 MiB Budget, einschließlich geschätzter dekodierter RGBA-Pixel und Bildzeichenfolgen. Aktuelle Seite und Nachbarn haben Vorrang; entfernte Seiten werden zuerst freigegeben. Ein bereits gemaltes aktives Bild bleibt während eines Austauschs zusätzlich sichtbar. |
| 5 | PDF-Quellen wiederverwenden | Geteilte PDF.js-Instanzen mit Nutzungs-Leases, maximal drei inaktive Quellen beziehungsweise 64 MiB Quelldaten. Aktive Renderaufträge dürfen zu Ende laufen; Wechsel und Schließen räumen auf. Temporäre Canvas-Puffer und PDF-Seitenoperatoren werden freigegeben. Auch der lokale Fallback berücksichtigt Graustufen und den kompatiblen Schwarzweißmodus. |
| 6 | Leichte Entwurfssicherung | Schema 2 trennt Metadaten von unveränderlichen Datei- und Miniaturdaten. Feldänderungen schreiben keine PDFs erneut. Referenzen bleiben auch über das Wiederherstellen hinaus erhalten. Neue Dateien werden für WebKit kompatibel einmalig als ArrayBuffer gespeichert. |
| 7 | Zuständigkeiten aufteilen | Eigene Module für kontinuierliches Scrollen, Bilddarstellung/Cache, PDF-Rendering, Analysewarteschlange, Formularfokus und Commit-Transaktion. Unbenutzte Funktionen und Styles früherer Importansichten wurden entfernt. |
| 8 | Zustände und Abbruch koordinieren | Explizite Analysephasen und feste Prozessprioritäten für Scan, Bereinigung, Upload, Analyse und Commit. Eine serielle Warteschlange schützt den Pi; entfernte oder geänderte Dokumente brechen auch Wartezeiten sofort ab. |
| 9 | Analysequalität reproduzierbar prüfen | Acht synthetische Fälle: Brief, Rechnung, Kündigung, Handschrift-Transkript, schlechter OCR-Text, mehrere Seiten, beschädigtes Datum und leerer Betreff. Getrennte Kennzahlen für Titel, Datum, Dokumenttyp, Absender und Notiz, einschließlich falscher positiver und fehlender Ergebnisse. |
| 10 | Entwürfe bei Fehlern schützen | Atomare Metadaten-/Dateitransaktionen, Migration aus Schema 1, Versionsvergleich bei parallelen Fenstern und Versionsmarkierung auch nach Löschung. Fehlgeschlagene Lese-/Quota-Vorgänge überschreiben keinen vorhandenen Entwurf. Eine neue Importtransaktion wird erst nach erfolgreicher lokaler Sicherung gesendet. Fehlende Quellen löschen weder Seiten noch Formulareingaben. |
| 11 | Browser und Belastung prüfen | Eigene Playwright-Matrix für Chromium, Firefox und WebKit. 100 Seiten, Layout-Zoom, native Einrastpunkte, Bildkontinuität, schnelle Navigation, Tastatur, Touch-Gesten, Quellenwechsel und Fehler bei der Sicherung. |
| 12 | Phasen intern messen | Begrenzter lokaler Diagnosepuffer für ersten Scan-Frame, erste scharfe Vorschau, erste Metadaten, Analyse, Entwurf und Commit. Server liefert numerische OCR-/KI-Zeiten. Keine Dokumenttexte, Namen, URLs oder Quell-IDs im Browser-Diagnosepuffer; kein Telemetrieversand und keine zusätzliche Statusanzeige. |

## Prüfbefehle

```sh
cd frontend
npm test
npm run build
npm run test:import:matrix -- --workers=3
```

Der Browserzugriff nutzt ausschließlich den lokalen Vite-Server unter `http://127.0.0.1:5179`. Die drei zu Playwright passenden Browserlaufzeiten müssen installiert sein.

```sh
docker compose exec -T backend python -m unittest \
  tests.test_import_quality_corpus tests.test_import_metadata_heuristics \
  tests.test_import_metadata_rules tests.test_import_title_formatting \
  tests.test_import_workflow_robustness tests.test_import_analysis_jobs

docker compose exec -T backend python -m scripts.evaluate_import_corpus
```

Der Korpusbericht enthält pro Feld Trefferquote, falsche positive Ergebnisse und fehlende Werte. Mit `--predictions DATEI.json` lassen sich aufgezeichnete Ergebnisse einer vollständigen OCR-/Modell-Pipeline gegen dieselben Erwartungen prüfen. Das Format steht im Evaluationsskript.

## Verifikation

- Frontend: 749 Tests bestanden.
- Backend: 43 Tests bestanden, darunter der acht Fälle umfassende Qualitätskorpus.
- Vollständige Browser-Matrix: 268 bestanden, zwei CDP-spezifische Touch-Prüfungen wie vorgesehen übersprungen.
- Lokaler PDF-Fallback einschließlich Farbmodus: anschließend sechs gezielte Prüfungen in Chromium, Firefox und WebKit bestanden.
- Produktionsbuild und Bundle-Budget bestanden; die vorhandene Warnung zu großen optionalen Chunks bleibt bestehen.
- Sichtprüfung der Desktopansicht und der eingerasteten scharfen Vorschau durchgeführt.

## Grenzen der automatisierten Prüfung

Der Offline-Korpus verwendet synthetische OCR-Transkripte und die echte regelbasierte Metadatenpipeline. Er misst keine Qualität echter handschriftlicher Bildvorlagen und keine Live-Modellgüte. Die Korrespondenten-Datenbank und die Namensvorlagen-Verfügbarkeit werden dafür isoliert. Es werden keine echten Dokumente, Scanneraufträge oder Modellanfragen ausgeführt.

Der native Touch-Swipe wird über Chromiums CDP injiziert. Firefox und WebKit prüfen Scrollen und Einrasten separat; diese CDP-spezifische Prüfung wird dort ausdrücklich übersprungen. Layout-Zoom wird mit CSS-Zoom geprüft und ist kein Ersatz für einen manuellen Test jeder Browser-/Betriebssystem-Zoomkombination. Vergrößerte Seiten lassen sich frei bis an den Inhaltssaum lesen; im eingepassten Zustand rasten die Seiten mittig ein.

Eine abrupt beendete Browserinstanz kann noch nicht abgeschlossene Schreibvorgänge verlieren. Der letzte vollständig geschriebene Entwurf bleibt erhalten; eine bereits vorbereitete Importanfrage wird für einen sicheren Wiederholungsversuch mit derselben Request-ID gespeichert.

Es wurde nichts auf dem Produktiv-Pi geändert. Commit, Push und Rollout sind nicht Teil dieses Umsetzungsauftrags.

## Ergänzung vom 22. Oktober: Schließen und verfügbare Seiten

Das Importfenster schließt ohne Verwerfen-Abfrage; Minimieren und die separate Entwurfsleiste entfallen. Nach der normalen Schließanimation wandert der letzte nicht leere Entwurf in einen eigenen verfügbaren Entwurf. Ein leeres Fenster ersetzt diesen Stand nicht. Der Startbildschirm öffnet ihn über „Verfügbare Seiten“ wieder, zusammen mit gegebenenfalls neuen Hintergrundseiten. Die Badge zählt aktive, abgelegte und neue Seiten ohne doppelt gezählte Quellen.

Dokumente, Seitenreihenfolge, Drehung, Farbmodus, Formularwerte, KI-Herkunft, PDF-Dateien und eine noch unbestätigte Importanfrage bleiben erhalten. Die vorhandene atomare IndexedDB-Sicherung speichert aktiven und verfügbaren Entwurf mit gemeinsamen unveränderlichen Assets und derselben Revisionsprüfung. Alte Quellen werden erst nach erfolgreicher Sicherung ihres Ersatzes aus dem Posteingang freigegeben. Neue Scans übernehmen den abgelegten Entwurf nicht automatisch. Ein erfolgreicher Import quittiert ausschließlich seine eigenen Quellen.

Uploads und Imports dürfen nach dem Schließen fertig werden. Ihr Ergebnis wird anschließend abgelegt, ohne das Fenster erneut zu öffnen. Eine verspätet heruntergeladene Quell-PDF wird auch dem bereits geschlossenen Entwurf zugeordnet. Ein offener, unbestätigter Import wird mit seiner bisherigen Request-ID fortgesetzt.
