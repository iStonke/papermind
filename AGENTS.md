# PaperMind – Hinweise für alle KI-Agenten

## Produktiv-Pi

Der Zugriff auf den Raspberry Pi läuft über die lokale, allow-gelistete
macOS-Bridge `com.papermind.pi-bridge`. Nie eine direkte Verbindung zu
`jan@papermind` voraussetzen und keine SSH-Befehle selbst zusammensetzen.

- Zulässige Pi-Aktionen über `python3 scripts/pi_bridge.py <aktion>`:
  `status`, `restore_drill`, `recovery_check`, `quiet_fan_profile`.
- `quiet_fan_profile` schreibt ausschließlich die fest hinterlegte, reversible
  PaperMind-Lüfterkennlinie in `/boot/firmware/config.txt`, legt zuvor eine
  Sicherung mit Suffix `.papermind-fan.bak` an und startet den Pi nicht neu.
  Ein Neustart ist separat und nur nach ausdrücklicher Freigabe auszuführen.
- Bei fehlender Bridge: `launchctl kickstart -k gui/$(id -u)/com.papermind.pi-bridge`.

Die Bridge ist nur über den lokalen Unix-Socket mit Berechtigung `0600`
erreichbar und verwendet `~/.ssh/id_rsa`. Niemals Schlüsselmaterial,
Passwörter oder frei formulierte Shell-Kommandos in die Bridge aufnehmen.

Weitere projektspezifische Hinweise stehen in `CLAUDE.md`.
