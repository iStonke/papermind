# PaperMind – Hinweise für KI-Agenten

## Raspberry Pi: lokaler, eingeschränkter Zugang

Für den Zugriff auf den Produktiv-Pi **immer** die lokale, allow-gelistete
Bridge `com.papermind.pi-bridge` verwenden. Sie läuft als macOS-LaunchAgent,
öffnet keinen Netzwerkport und führt ausschließlich feste PaperMind-Operationen
im Mac-Benutzerkontext aus.

- Aufrufe nur über `python3 scripts/pi_bridge.py <aktion>`: `status`,
  `restore_drill`, `recovery_check` oder `quiet_fan_profile`.
- `quiet_fan_profile` schreibt nur die fest hinterlegte, reversible
  PaperMind-Lüfterkennlinie nach `/boot/firmware/config.txt`, sichert die
  vorherige Datei als `.papermind-fan.bak` und löst keinen Neustart aus.
  Den dafür erforderlichen Neustart nie ohne ausdrückliche Freigabe ausführen.
- Falls die Bridge nicht erreichbar ist, den Dienst gezielt neu starten:
  `launchctl kickstart -k gui/$(id -u)/com.papermind.pi-bridge`.
- Der Unix-Socket ist auf `0600` beschränkt. Nie frei formulierte
  Shell-Kommandos, Passwörter oder Schlüsselmaterial in die Bridge aufnehmen.

## Lokale Frontend-Entwicklung: immer den Vite-Dev-Server auf 5179 nutzen

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
