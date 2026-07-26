# PaperMind – Hinweise für alle KI-Agenten

## Produktiv-Pi

Der dauerhafte Zugriff auf den Raspberry Pi läuft über den macOS-LaunchAgent
`com.papermind.ssh-tunnel`. Nie eine direkte Verbindung zu
`jan@papermind` voraussetzen.

- Vor Pi-Aktionen: `nc -vz 127.0.0.1 2222`
- Pi-Kommandos: `ssh -S /tmp/papermind-ssh-control.sock -o HostKeyAlias=papermind-pi-lan jan@192.168.178.92 '<befehl>'`
- Bei fehlendem Tunnel: `launchctl kickstart -k gui/$(id -u)/com.papermind.ssh-tunnel`

Der Dienst verwendet `~/.ssh/id_rsa`. Niemals Schlüsselmaterial oder
Passwörter auslesen, anzeigen oder ins Repository aufnehmen.

Weitere projektspezifische Hinweise stehen in `CLAUDE.md`.
