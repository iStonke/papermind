# Performance und Stabilität – September 2026

## Umgesetzte Änderungen

1. **Kurze Indextransaktionen.** Embeddings werden vor der schreibenden
   Datenbanktransaktion berechnet. Vor der Veröffentlichung werden Dokumentversion,
   Quelldatei und Job-Lease erneut geprüft. Migration `094_backup_change_journal`
   ersetzt den zentralen Dirty-Counter-Trigger durch ein transaktionales Journal.
   Unabhängige Dokumentänderungen blockieren dadurch nicht mehr dieselbe Counter-Zeile.
   Backup-Abschluss verdichtet nur den bestätigten, sichtbaren Journalstand;
   später commitende Transaktionen bleiben als neue Änderungen erhalten.
2. **Abgesicherte Job-Ergebnisse.** Der Worker sperrt und prüft die Job-Zeile vor
   der Veröffentlichung. Ein abgelaufener oder neu vergebener Lease darf keine
   Ergebnisse mehr veröffentlichen. OCR arbeitet in einem eigenen temporären
   Verzeichnis und veröffentlicht unter einem unveränderlichen Dateinamen pro
   Versuch. Die bisherige OCR-Datei wird nicht überschrieben. Ein Abbruch zwischen
   Dateiveröffentlichung und DB-Commit kann eine unreferenzierte Datei hinterlassen,
   aber keine bisher gültige Dateireferenz zerstören.
3. **Gemeinsame Backup-Schreibsperre.** HTTP-Schreibanfragen, Worker und dessen
   Hintergrundaufgaben halten eine gemeinsame Dateisperre. Wartung sperrt zunächst
   neue Zulassungen und wartet danach auf laufende Schreibvorgänge. Neue Anfragen
   erhalten währenddessen HTTP 503 mit Retry-After. GET-Streams geben ihre Sperre
   nach den Response-Headern frei. Eine zweite Wartung wird ausgeschlossen; bei
   Fehlern während ihrer Vorbereitung werden Marker und Sperren wieder freigegeben.
4. **Reproduzierbare Tests.** Isolierter Docker-Testlauf mit echten Migrationen,
   PostgreSQL/pgvector, App-/Worker-Rollen und OCR-Abhängigkeiten. CI migriert vor
   den Tests und akzeptiert keine übersprungenen Backend-Tests. Neue Verhaltenstests
   decken konkurrierende Indexänderungen, Backup-Journal, veraltete Leases,
   Wartungssperren, Worker-Spuren und Frontend-Lebenszyklen ab.
5. **Kleinerer Frontend-Start.** Der Notiz-Entwicklungsharness wird nur im
   Entwicklungsmodus asynchron geladen. PDF.js zieht nicht mehr über den gemeinsamen
   Preload-Helfer in den initialen Importgraphen ein. Das Build-Budget begrenzt
   initiales JavaScript auf 600 KiB unkomprimiert und 200 KiB gzip und verhindert
   bekannte schwere Module im Startgraphen. Der geprüfte Build benötigt
   **505,3 KiB unkomprimiert / 169,5 KiB gzip** in fünf initialen JS-Chunks.
   CSS, Fonts und später geladene Funktionen sind in dieser Messung nicht enthalten.
6. **Worker und Workspace entkoppelt.** Eine OCR-Spur und eine INDEX/TAG-Spur
   erlauben Metadaten-/Indexarbeit neben OCR. Pro Spur wird nur ein Job beansprucht;
   die Import-Hauptschleife wartet nicht mehr synchron auf Dokumentjobs. Autosave,
   Import-Inbox-Synchronisierung, PDF-Auswahl und Styles sind aus dem großen
   Workspace ausgelagert. Tests schützen insbesondere neuere Entwürfe bei verspäteten
   Speicherantworten und verhindern wiederkehrende Polling-Timer nach dem Schließen.

Die kompatiblen Frontend-Abhängigkeiten wurden aktualisiert. TipTap-Pakete sind
einheitlich auf 3.31.3 fixiert; PDF.js bleibt auf 5.4.624. Das abschließende
Paket-Audit meldete keine bekannten Schwachstellen im aufgelösten Abhängigkeitsbaum.

## Nachweise und Grenzen

- Backend: 439 bestandene Tests, keine übersprungenen Tests; Migration 094 wurde
  zusätzlich auf einer isolierten Datenbank zurück- und wieder vorwärts ausgeführt.
- Frontend: 479 bestandene Unit-Tests, Produktionsbuild einschließlich Budgetprüfung.
- Browser: vier bestandene Tests auf Vite 127.0.0.1:5179 für Login, PDF-Import,
  Metadaten-Autosave mit Reload und den echten Notizeditor mit Reload.
  API-Antworten werden dabei simuliert; dies ist kein vollständiger End-to-End-Test
  gegen die laufende Datenbank oder den Scanner.
- Dies sind lokale Funktions- und Build-Nachweise. Es wurde kein Produktionslasttest
  durchgeführt und keine konkrete Beschleunigung auf dem Raspberry Pi gemessen.

## Produktionsupdate

Der Stand ist im Repository umgesetzt; der Produktiv-Pi wurde nicht aktualisiert.
Backend und Worker benötigen dieselbe neue Codeversion, Migration 094 und denselben
beschreibbaren Storage-Pfad für die Dateisperren. Bei `BACKUP_STATE_PATH` muss auch
dieser Pfad zwischen beiden Containern geteilt sein. Alte und neue Worker dürfen
während der Umstellung nicht parallel produktiv schreiben, da alte Prozesse die
neue Schreibsperre nicht berücksichtigen. Das Dateisystem muss POSIX-flock unterstützen.

Vor dem geplanten Update eine aktuelle Sicherung sicherstellen. Beim Rollout alte
Schreiber beenden, Migration ausführen und Backend/Worker gemeinsam auf dem neuen
Stand starten. Bei einem Rollback entsprechend alle neuen Schreiber zuerst stoppen,
Migration zurücksetzen und dann die alte Codeversion starten. Die bisherigen
Dateireferenzen bleiben gültig.

Nach dem Update Laufzeit, Queue-Wartezeit, Fehlerraten, CPU/RAM und Backup-Dauer
unter echten Importen beobachten. Insbesondere die zusätzliche Worker-Parallelität
auf dem Pi prüfen. Für Agenten bleibt der Pi-Zugriff auf die in AGENTS.md/CLAUDE.md
erlaubten Bridge-Aktionen beschränkt; die Bridge bietet kein Deployment an.

Der Workspace ist weiterhin groß. Die ausgelagerten Verantwortlichkeiten erleichtern
weitere Zerlegung, ersetzen aber keine vollständige Aufteilung der Oberfläche.
