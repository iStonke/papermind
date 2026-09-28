# PaperMind – Hinweise für alle KI-Agenten

## Produktiv-Pi

Der Zugriff auf den Raspberry Pi läuft über die lokale, allow-gelistete
macOS-Bridge `com.papermind.pi-bridge`. Nie eine direkte Verbindung zu
`jan@papermind` voraussetzen und keine SSH-Befehle selbst zusammensetzen.

- Zulässige Pi-Aktionen über `python3 scripts/pi_bridge.py <aktion>`:
  `status`, `scanner_status`, `scanner_calibration_test`,
  `scanner_calibration_restore`, `scanner_timing_test`, `scanner_timing_restore`,
  `scanner_jpeg_test`, `scanner_jpeg_restore`, `restore_drill`, `recovery_check`,
  `quiet_fan_profile`.
- `scanner_status` liest ausschließlich Dienststatus, feste systemd-Definitionen,
  Canon-USB-Energiezustand, SANE-Geräteliste und begrenzte Scanner-Logs aus.
- `scanner_calibration_test` sichert das Scan-Skript und aktiviert darin
  reversibel `SCAN_CALIBRATE=Never`; ein Dienstneustart ist nicht erforderlich.
- `scanner_calibration_restore` stellt das Scan-Skript aus dieser Sicherung
  wieder her.
- `scanner_timing_test` sichert das Scan-Skript und überträgt ausschließlich die
  feste lokale Projektversion mit Phasen-Zeitmessung; `scanner_timing_restore`
  stellt die Sicherung wieder her.
- `scanner_jpeg_test` aktiviert nach Sicherung reversibel das direkte JPEG-
  Scanformat; `scanner_jpeg_restore` stellt die Sicherung wieder her.
- `quiet_fan_profile` schreibt ausschließlich die fest hinterlegte, reversible
  PaperMind-Lüfterkennlinie in `/boot/firmware/config.txt`, legt zuvor eine
  Sicherung mit Suffix `.papermind-fan.bak` an und startet den Pi nicht neu.
  Ein Neustart ist separat und nur nach ausdrücklicher Freigabe auszuführen.
- Bei fehlender Bridge: `launchctl kickstart -k gui/$(id -u)/com.papermind.pi-bridge`.

Die Bridge ist nur über den lokalen Unix-Socket mit Berechtigung `0600`
erreichbar und verwendet `~/.ssh/id_rsa`. Niemals Schlüsselmaterial,
Passwörter oder frei formulierte Shell-Kommandos in die Bridge aufnehmen.

Weitere projektspezifische Hinweise stehen in `CLAUDE.md`.
