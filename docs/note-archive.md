# Notizen exportieren und importieren

Im Dreipunkt-Menü einer geöffneten Notiz:

- **Notiz exportieren** lädt eine `.papermind.json`-Datei herunter. Vorher wird die Notiz gespeichert; bei einem Speicherkonflikt wird der Export abgebrochen.
- **Notiz importieren** liest diese Datei und legt eine neue Notiz an. Bestehende Notizen werden nicht überschrieben.

Das versionierte Format enthält Titel, die vollständige Editorstruktur (einschließlich Formatierungen, Tabellen, Aufgaben und Blockattributen), alle gespeicherten Notizbilder als unveränderte Dateibytes, Tags, Favoritenstatus, Sammlung, Notizbuch, Zeitstempel und Versionsverlauf. Neue interne IDs werden beim Import vergeben; Bildverweise und Selbstverweise werden angepasst. Aufgaben und ausgehende Verweise werden neu indiziert.

Sammlungen und Notizbücher werden nach Namen im eigenen Konto wiederverwendet oder bei Bedarf angelegt. Bereits vorhandene Ablagen werden nicht umgestaltet. Verweise auf andere Notizen und Dokumente bleiben Verweise: Die verknüpften Objekte selbst gehören nicht zum Notizarchiv und müssen im Zielsystem vorhanden sein.

Die maximale Dateigröße beträgt 100 MB. Unbekannte Formatversionen, unvollständige Bildbestände und ungültige Bilddateien werden zurückgewiesen. Ein fehlgeschlagener Import wird vollständig zurückgerollt.

Markdown und PDF bleiben als zusätzliche Ausgabeformate verfügbar; für den vollständigen Wiederimport ist die PaperMind-Datei vorgesehen.
