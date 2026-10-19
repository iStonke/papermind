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

Die Anwendung bestand 674 Backendtests und 48 Untertests, 733 Frontendtests, 28 Browserprüfungen sowie den Produktionsbuild mit Größenbudgets. 81 zusätzliche Rollout- und Bridgeprüfungen sind erfolgreich, einschließlich Paket- und Quellprüfung, fester Argumente, Abbruch vor dem Wechsel, Sicherungsreihenfolge, Migration, Rückfall, Bridge-Installation und Statusprüfung unter Wartung. Paket und Entpackschutz wurden mit dem tatsächlichen Release-Archiv lokal ausgeführt.

## Korrektur des Prüfers und kontrollierter Rückfall

Der erste Versuch erstellte die erfolgreiche verschlüsselte Sicherung `2b4323c9-3bc7-4115-b901-d974092ba9e1` mit 1.231.696.434 Byte. Die anschließende Zugriffsprüfung erwartete fälschlich HTTP 401, obwohl die aktive Schreibbarriere vor der Authentifizierung korrekt HTTP 503 zurückgab. Der automatische Rückfall bestätigte Schema 113, den sauberen Ausgangscommit und gesunde bisherige Dienste.

Der korrigierte Prüfer erwartet während der Wartung HTTP 503 und verlangt nach deren Freigabe weiterhin HTTP 401. Neue Verhaltenstests prüfen beide Zustände und die Ablehnung falscher Statuscodes oder erfolgreichen anonymen Zugriffs. Die Bridge darf ausschließlich den bekannten vorherigen Runner mit SHA-256 `b58161564fa49a175d49a740db1746b64d31fffca274802f3f1e54fb60543f4d` ersetzen, wenn der Rückfall als erfolgreich bestätigt ist und Git wieder exakt auf dem festgelegten Ausgangsstand steht. Ein laufender oder unbekannt veränderter Runner wird nicht ersetzt.

Beim Wiederholungsversuch darf die weniger als eine Stunde alte Sicherung übernommen werden. Dazu werden der passende erfolgreiche Sicherungslauf, Zeitpunkt, NAS-Zuordnung, Manifest-HMAC, Schema, Artefaktnamen, Größen und sämtliche SHA-256 erneut geprüft. Es wird kein ungeprüftes oder unvollständiges Backup akzeptiert.

## Produktiver Abschluss

Die abschließende Prüfung am 19. Oktober 2026 um 21:49 UTC (23:49 MESZ) ist erfolgreich. Produktiv laufen Commit `8d87348e079477d304a61523e5a7187155187f2b` und Schema `114_import_receipts`. Alle sechs Dienste sind gesund; DB, AI und Caddy behalten ihre vorherigen Container und Images.

Die Sicherung `2b4323c9-3bc7-4115-b901-d974092ba9e1` wurde vor dem erfolgreichen Wiederholungsversuch vollständig erneut verifiziert. Der Runner meldet `status=success`, `phase=complete` und `reused_verified_backup=true`. Die verschlüsselte lokale Wiederherstellungskopie und die NAS-Sicherung bleiben erhalten.

Die feste Abschlussprüfung bestätigt ausdrücklich, dass die Wartung freigegeben ist und der echte HTTP-Aufruf ohne Anmeldung mit **401** abgewiesen wird. Zusätzlich sind Produktionskonfiguration und RLS-Webrolle, aktuelle Anwendungsrevision, Schema, Importbestätigungsindex, Chunk-Suchindex, eine kontogebundene Notizabfrage sowie Backend- und Frontend-Bereitschaft bestätigt. Es gab keinen Pi-Neustart, keine Host-Updates und keine Änderung echter `.env`-Dateien.

Die Anwendungsänderungen und die separat versionierten Rollout-Werkzeuge sind im Branch `feat/ki-chat-integration` committed und gepusht. Der Pi bleibt bewusst auf dem festen Anwendungscommit; nachfolgende Werkzeug- und Protokollcommits ändern das Anwendungspaket nicht. Für die neue Oberfläche muss ein bereits offener Browser-Tab neu geladen werden.
