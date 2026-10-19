# Importrollout vom 19. Oktober 2026

Der Nutzer hat Commit, Push und produktiven Pi-Rollout der Importverbesserungen einschließlich der durchgehenden Scanvorschau beauftragt. Die vorhandene lokale Unix-Socket-Bridge erhält dafür fünf zusätzliche feste Aktionen. Es werden keine frei wählbaren Befehle, Hosts, Pfade oder Releases angenommen. Ein Pi-Neustart und Host-Updates gehören nicht zum Ablauf.

- Ausgangsstand: `575d9b375f9ebde219f72df8bb7f5a86df72e529`.
- Ziel: `8d87348e079477d304a61523e5a7187155187f2b`, Branch `feat/ki-chat-integration`.
- Archiv-SHA-256: `93ae3ca356f66b9c7beb11396160ac511b15a1be37bb0a7ca2bc5c74d9108f7c`.
- Paket: 1.072 reguläre Dateien, 2.081.888 Byte. Die unveränderten statischen Dateien unter `deploy/host-control` bleiben außerhalb des Transferpakets; sie sind im Zielcommit enthalten. Tatsächliche Steuerdateien, Dokumente, `.env`-Dateien, Schlüssel, Git-Metadaten und lokale Laufzeitdaten sind ausgeschlossen.
- Schema: `113_drop_note_favorite` → `114_import_receipts`.
- Geänderte Dienste: Backend, Worker, Frontend. DB, AI und Caddy werden nicht neu erstellt.

Das [Release-Manifest](../deploy/import-release-2026-10-19.json) pinnt zusätzlich beide Runner-Dateien. Der [lokale Installer](../scripts/install_pi_import_release_bridge.py) prüft Manifest, Runner und Paket, sichert die bestehende Bridge und ergänzt ausschließlich `import_release_inspect`, `import_release_prepare`, `import_release_apply`, `import_release_status` und `import_release_verify`. Die bisherigen Aktionen bleiben bestehen. Die Bridge behält ihren privaten Socket und ihre bestehende Host-Key-Prüfung.

## Ablauf

1. Produktionsrevision, unveränderte versionierte Quellen, gesunde Dienste sowie freie Ressourcen prüfen. Laufende Jobs, Scans, Sicherungen und Wartung schließen den Wechsel aus.
2. Den geprüften Snapshot in einem privaten Staging-Verzeichnis entpacken und die drei Images bauen. Die Produktionscontainer bleiben dabei bestehen. Kandidaten müssen die Produktionskonfiguration, Rollen, Backup-Schlüsselverfügbarkeit und benötigten Laufzeitabhängigkeiten bestätigen.
3. Eine frische verschlüsselte Sicherung mit dem bestehenden Backup-Service erstellen. NAS-Veröffentlichung, lokales Wiederherstellungsexemplar, Manifest-HMAC, Schema, Zeitpunkt, Artefaktnamen, Größen und SHA-256 werden geprüft. Es wird keine bestehende Sicherung gelöscht.
4. Die bestehende Schreibbarriere aktivieren, laufende Schreibvorgänge beenden lassen und erst dann Backend, Worker und Frontend stoppen. Git wechselt ausschließlich per Fast-forward zum festgelegten Commit. Migration 114 ergänzt den eindeutigen Index für Importbestätigungen.
5. Neue Dienste starten und Gesundheit, RLS-Konfiguration, Schema, Importindex, Anwendungsrevision und Ablehnung anonymer Dokumentzugriffe prüfen. Bisherige Image-IDs bleiben für einen Rückfall verfügbar; normale Image-Tags werden erst nach erfolgreicher Prüfung aktualisiert.
6. Schreibbarriere freigeben und abschließend über die feste Bridge prüfen. Ein Fehler während des Wechsels stellt Schema 113, den vorherigen sauberen Git-Stand und die alten Images wieder her; Nutzerdaten werden nicht aus einem älteren Backup überschrieben.

## Validierung vor dem Wechsel

Die Anwendung bestand 674 Backendtests und 48 Untertests, 733 Frontendtests, 28 Browserprüfungen sowie den Produktionsbuild mit Größenbudgets. Der neue Runner wird zusätzlich isoliert auf Paket- und Quellprüfung, feste Argumente, Abbruch vor dem Wechsel, Sicherungsreihenfolge, Migration, Rückfall und Bridge-Installation geprüft. Paket und Entpackschutz werden mit dem tatsächlichen Release-Archiv lokal ausgeführt.

## Produktiver Abschluss

Der tatsächliche Versions-, Sicherungs- und Dienststatus wird nach dem Rollout hier ergänzt.
