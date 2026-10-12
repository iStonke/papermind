# PaperMind – Hinweise für alle KI-Agenten

## Produktiv-Pi

Der Zugriff auf den Raspberry Pi läuft über die lokale, allow-gelistete
macOS-Bridge `com.papermind.pi-bridge`. Nie eine direkte Verbindung zu
`jan@papermind` voraussetzen und keine SSH-Befehle selbst zusammensetzen.

- Zulässige Pi-Aktionen über `python3 scripts/pi_bridge.py <aktion>`:
  `status`, `scanner_status`, `scanner_calibration_test`,
  `scanner_calibration_restore`, `scanner_timing_test`, `scanner_timing_restore`,
  `scanner_jpeg_test`, `scanner_jpeg_restore`, `scanner_poller_restart`,
  `restore_drill`, `recovery_check`, `quiet_fan_profile`.
- Zusätzlich ausdrücklich freigegeben: `rollout` und `rollout_status` für den
  fest gepinnten Optimierungs-Release vom 11. Oktober 2026. `rollout` überträgt
  ausschließlich das geprüfte Paket mit fester SHA-256-Prüfsumme, erstellt eine
  Sicherung, baut die Images, migriert und prüft den Wiederanlauf. Kein
  frei wählbarer Befehl, Host oder Pfad und kein Pi-Neustart. `rollout_status`
  liest nur den begrenzten Fortschritt dieses Releases.
- `rollout_verify` führt ausschließlich die feste abschließende Prüfung des
  erfolgreich installierten Releases aus: RLS, anonymen Zugriff, synthetisches
  PDF, lokale Piper-Ausgabe und HTTP-Kompression. Keine Nutzerdatenänderung.
- Zusätzlich ausdrücklich freigegeben: `git_reconcile_status` und
  `git_reconcile` für den Git-Abgleich des geprüften Snapshots auf Commit
  `20e59e1e4c32d8e68117862e520dc1bf4e4da6f3`, einschließlich der bereits aktiven
  Notizkorrektur. Feste Quelle/Branch/Dateihashes, Sicherung vor Änderungen und
  Abbruch bei unbekannten Abweichungen. Keine freien Parameter, Container-
  Neustarts, Migrationen oder Änderungen an Nutzerdaten und echten `.env`-Dateien.
- Zusätzlich ausdrücklich freigegeben: `performance_audit`,
  `performance_audit_status` und `security_inventory` für die Prüfung vom
  12. Oktober 2026 auf dem festen Stand `acc22ca`. Höchstens zwei parallele
  GETs und vier Anfragen pro Sekunde, feste Dauer-/Größen-/Ressourcengrenzen.
  Die Inventur liest ausschließlich öffentliche Paket-/Laufzeitmetadaten;
  der Schwachstellenabgleich erfolgt lokal auf dem Mac. Keine freien Parameter,
  Dokumentänderungen, Updates, Container-Neustarts oder Pi-Neustarts.
- `scanner_status` liest ausschließlich Dienststatus, feste systemd-Definitionen,
  Canon-USB-Energiezustand, SANE-Geräteliste und begrenzte Scanner-Logs aus.
- Der Auftrag zur Umsetzung des Sicherheits-Patch-Releases vom 12. Oktober
  umfasst die feste zusätzliche Aktion `security_patch_inspect`: ausschließlich
  begrenzte lesende SQL-Planmessungen auf Stand `acc22ca` und UID/GID/Modus der
  bestehenden Container-Mounts. Keine Dokumenttexte, IDs oder Geheimnisse im
  Ergebnis; keine freien Parameter und keine Paket-/Dienständerungen.
- `scanner_calibration_test` sichert das Scan-Skript und aktiviert darin
  reversibel `SCAN_CALIBRATE=Never`; ein Dienstneustart ist nicht erforderlich.
- Der ausdrücklich beauftragte Sicherheitsrollout ist an Release `01d1c53`,
  Archiv-SHA `1fd05022e17d55df664de78c80c2e0c9a61aa32f0c2ab7d4751f53450176ec30`,
  Ausgangsstand `acc22ca` und die offline geprüften Paketversionen gebunden.
  Feste zusätzliche Aktionen: `security_patch_prepare`, `security_patch_rollout`,
  `security_patch_status`, `security_patch_inventory`, `security_patch_verify`,
  `security_patch_measure`, `security_patch_measure_status`,
  `security_patch_live_inventory`, `security_patch_host_plan`,
  `security_patch_host_apply`, `security_patch_host_status`.
  Staging ohne Live-Wechsel; Rollout mit frischer verifizierter verschlüsselter
  Sicherung, Schreibsperre, gesichertem UID-Wechsel und Rückfall. Host-Updates
  erfolgen separat, nur für die feste Sicherheitsauswahl mit unverändertem
  simuliertem Versionsplan, ohne Paketentfernung und ohne Kernel-/Docker-/
  systemd-/SSH-Umstellung. Keine freien Parameter, echten `.env`-Änderungen oder
  Pi-Neustarts. Diagnosen behalten die bisherigen GET-/Ressourcengrenzen.
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
- `scanner_poller_restart` prüft, dass der installierte Tasten-Poller den
  vierfeldrigen Scanbefehl samt Job-ID unterstützt, und startet ausschließlich
  `papermind-scan-watch.service` neu.
- `quiet_fan_profile` schreibt ausschließlich die fest hinterlegte, reversible
  PaperMind-Lüfterkennlinie in `/boot/firmware/config.txt`, legt zuvor eine
  Sicherung mit Suffix `.papermind-fan.bak` an und startet den Pi nicht neu.
  Ein Neustart ist separat und nur nach ausdrücklicher Freigabe auszuführen.
- Bei fehlender Bridge: `launchctl kickstart -k gui/$(id -u)/com.papermind.pi-bridge`.

Die Bridge ist nur über den lokalen Unix-Socket mit Berechtigung `0600`
erreichbar und verwendet `~/.ssh/id_rsa`. Niemals Schlüsselmaterial,
Passwörter oder frei formulierte Shell-Kommandos in die Bridge aufnehmen.

Weitere projektspezifische Hinweise stehen in `CLAUDE.md`.

Host-Sicherheitsupdates dieses Releases verwenden nach manueller Einrichtung
den root-eigenen Helfer `/usr/local/libexec/papermind-security-20261012`.
Sudoers pinnt dessen SHA-256; nur `update`, `plan`, `download`, `verify`,
`install` sind zulässig. Keine Passworteingabe über die Bridge. Anleitung:
`docs/host-security-setup-2026-10-12.md`. Reine APT-Vorbereitung darf während
der Rollout-Sicherung stattfinden; Installation benötigt den gesunden Zielstand.
