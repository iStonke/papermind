# PaperMind – Hinweise für KI-Agenten

## Raspberry Pi: lokaler, eingeschränkter Zugang

Für den Zugriff auf den Produktiv-Pi **immer** die lokale, allow-gelistete
Bridge `com.papermind.pi-bridge` verwenden. Sie läuft als macOS-LaunchAgent,
öffnet keinen Netzwerkport und führt ausschließlich feste PaperMind-Operationen
im Mac-Benutzerkontext aus.

- Aufrufe nur über `python3 scripts/pi_bridge.py <aktion>`: `status`,
  `scanner_status`, `scanner_calibration_test`, `scanner_calibration_restore`,
  `scanner_timing_test`, `scanner_timing_restore`, `scanner_jpeg_test`,
  `scanner_jpeg_restore`, `scanner_poller_restart`, `restore_drill`,
  `recovery_check` oder `quiet_fan_profile`.
- Für den Optimierungs-Release vom 11. Oktober 2026 hat der Nutzer außerdem
  `rollout` und `rollout_status` ausdrücklich freigegeben: festes Paket mit
  Prüfsumme, Sicherung, Image-Build, Migration, Gesundheitsprüfung und
  Wiederanlauf mit vorherigen Images bei Fehlern. Kein frei wählbarer Befehl,
  Host oder Pfad und kein Pi-Neustart.
- `rollout_verify` prüft ausschließlich diesen erfolgreich installierten Release
  mit synthetischem PDF/Sprachtext, Zugriffskontrolle und HTTP-Kompression.
- `git_reconcile_status` und `git_reconcile` sind ausdrücklich für den festen
  Git-Abgleich auf `20e59e1e4c32d8e68117862e520dc1bf4e4da6f3` freigegeben:
  bekannte Dateihashes, Quellsicherung und Abbruch bei unbekannten Änderungen.
  Die bereits aktive Notizkorrektur bleibt erhalten; keine freien Parameter,
  Container-Neustarts, Migrationen oder Änderungen an echten `.env`-Dateien.
- Für die Prüfung vom 12. Oktober 2026 sind `performance_audit`,
  `performance_audit_status` und `security_inventory` ausdrücklich freigegeben:
  fester Stand `acc22ca`, maximal zwei parallele GETs / vier Anfragen pro Sekunde,
  feste Ressourcen-/Laufzeitgrenzen und öffentliche Paket-/Laufzeitmetadaten.
  Keine freien Parameter, Dokumentänderungen, Updates oder Neustarts.
- `scanner_status` liest ausschließlich Dienststatus, feste systemd-Definitionen,
  Canon-USB-Energiezustand, SANE-Geräteliste und begrenzte Scanner-Logs aus.
- Der Umsetzungsauftrag für den Sicherheitsrelease vom 12. Oktober umfasst
  `security_patch_inspect`: feste lesende SQL-Planmessungen auf Stand `acc22ca`
  und UID/GID/Modus bestehender Mounts; keine Inhalte, IDs, Geheimnisse oder
  Paket-/Dienständerungen und keine freien Parameter.
- `scanner_calibration_test` sichert das Scan-Skript und aktiviert darin
  reversibel `SCAN_CALIBRATE=Never`; ein Dienstneustart ist nicht erforderlich.
- Der beauftragte Sicherheitsrelease `01d1c53` ist fest an Archiv-SHA
  `1fd05022e17d55df664de78c80c2e0c9a61aa32f0c2ab7d4751f53450176ec30`,
  Basis `acc22ca` und offline geprüfte Pakete gebunden. Zusätzliche feste Aktionen:
  `security_patch_prepare`, `security_patch_rollout`, `security_patch_status`,
  `security_patch_inventory`, `security_patch_verify`, `security_patch_measure`,
  `security_patch_measure_status`, `security_patch_live_inventory`,
  `security_patch_host_plan`, `security_patch_host_apply`, `security_patch_host_status`.
  Sicherung, Schreibsperre, reversible Eigentümermigration, fester Git-Abgleich
  und Image-Rückfall. Separate Host-Patches ohne Entfernung, Kernel-/Docker-/
  systemd-/SSH-Wechsel oder Neustart; keine freien Parameter oder `.env`-Änderung.
- `scanner_calibration_restore` stellt das Scan-Skript aus dieser Sicherung
  wieder her.
- Separat ausdrücklich freigegeben am 12. Oktober 2026: ein kontrollierter
  Pi-Neustart mit `security_patch_restart`, um die installierten Host-Patches
  in SSH und D-Bus zu aktivieren. Fest an `01d1c53` und die erfolgreiche
  Host-Installation gebunden; verifizierte Sicherung, gesunde Dienste und keine
  aktiven/queued Jobs, Backups, Wartung oder Power-Aktionen. Bestehende feste
  Host-Steuerung, Schreibsperre und einmalige Zulassung; keine freien Parameter.
  `security_patch_host_status` prüft anschließend den Boot-Wechsel und die
  geladenen Bibliotheksmetadaten. Dies erlaubt keinen weiteren Pi-Neustart.
- `scanner_timing_test` sichert das Scan-Skript und überträgt ausschließlich die
  feste lokale Projektversion mit Phasen-Zeitmessung; `scanner_timing_restore`
  stellt die Sicherung wieder her.
- `scanner_jpeg_test` aktiviert nach Sicherung reversibel das direkte JPEG-
  Scanformat; `scanner_jpeg_restore` stellt die Sicherung wieder her.
- `scanner_poller_restart` validiert den vierfeldrigen Scanbefehlparser und
  startet ausschließlich `papermind-scan-watch.service` neu.
- `quiet_fan_profile` schreibt nur die fest hinterlegte, reversible
  PaperMind-Lüfterkennlinie nach `/boot/firmware/config.txt`, sichert die
  vorherige Datei als `.papermind-fan.bak` und löst keinen Neustart aus.
  Den dafür erforderlichen Neustart nie ohne ausdrückliche Freigabe ausführen.
- Falls die Bridge nicht erreichbar ist, den Dienst gezielt neu starten:
  `launchctl kickstart -k gui/$(id -u)/com.papermind.pi-bridge`.
- Der Unix-Socket ist auf `0600` beschränkt. Nie frei formulierte
  Shell-Kommandos, Passwörter oder Schlüsselmaterial in die Bridge aufnehmen.

## Lokale Frontend-Entwicklung: immer den Vite-Dev-Server auf 5179 nutzen

Der beauftragte Importrollout vom 19. Oktober verwendet die in `AGENTS.md`
genannten festen Aktionen `import_release_inspect`, `import_release_prepare`,
`import_release_apply`, `import_release_status` und `import_release_verify`.
Commit und Archiv-Prüfsumme stehen in `deploy/import-release-2026-10-19.json`.
Keine freien Parameter, Host-Updates, echten `.env`-Änderungen oder Pi-Neustarts.

Zum Prüfen von Frontend-Änderungen **immer den Vite-Dev-Server** verwenden, der
unter **`http://127.0.0.1:5179`** läuft. Das lokale `docker-compose.yml` startet
`papermind-frontend` deshalb ebenfalls als Vite-Dev-Container mit Live-Mount der
Quellen; nur `docker-compose.prod.yml` verwendet den statischen nginx-Build.

- **`127.0.0.1:5179` = Vite-Dev-Server** (lokaler Compose-Service oder
  `npm run dev` im Ordner `frontend/`).
  Liefert die Live-Quellen mit HMR und proxyt `/api` zum Backend auf Port 8040
  (`backend:8040` in Compose, `localhost:8040` beim Host-Start). Änderungen sind
  sofort sichtbar.
- Der lokale **Docker-Container `papermind-frontend`** bind-mountet `frontend/`
  und synchronisiert seine Linux-Abhängigkeiten bei jedem Start mit
  `package-lock.json`. `docker compose restart frontend` zeigt deshalb weiterhin
  den aktuellen Arbeitsstand; ein Image-Rebuild ist für Quellcodeänderungen nicht
  erforderlich.
- Falls der Compose-Dev-Server nicht läuft: `docker compose up -d frontend`. Für
  einen bewusst direkt auf dem Host gestarteten Dev-Server zuerst
  `docker compose stop frontend`, dann im Ordner `frontend/` `npm run dev` starten.
- **Immer über die IPv4-Adresse `http://127.0.0.1:5179` öffnen**, nicht `localhost`:
  macOS löst `localhost` zuerst nach IPv6 `::1` auf, wo parallele Dev-Server binden
  und den eigenen Server verdecken können.
- Backend, DB, AI und Worker laufen in Docker und bleiben stehen.

Host-Sicherheitsupdates dieses Releases verwenden nach manueller Einrichtung
den root-eigenen Helfer `/usr/local/libexec/papermind-security-20261012`.
Sudoers pinnt dessen SHA-256; nur `update`, `plan`, `download`, `verify`,
`install` sind zulässig. Keine Passworteingabe über die Bridge. Anleitung:
`docs/host-security-setup-2026-10-12.md`. Reine APT-Vorbereitung darf während
der Rollout-Sicherung stattfinden; Installation benötigt den gesunden Zielstand.
