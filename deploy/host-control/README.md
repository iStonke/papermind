# PaperMind Host-Control

Damit die Buttons **Herunterfahren** und **Neustarten** in den Einstellungen
(Bereich *System*) den Raspberry Pi wirklich steuern können, braucht es einen
kleinen Helfer auf dem **Host** – ein Docker-Container darf den Host selbst
nicht ausschalten.

## Funktionsweise

1. Das Backend schreibt bei einem Klick eine Datei `command` in das geteilte
   Verzeichnis (`HOST_CONTROL_DIR`, gemountet als `/host/control` im Container).
2. Der Host-Service [`papermind-host-control.sh`](./papermind-host-control.sh)
   überwacht dieses Verzeichnis, liest das Kommando (`poweroff` / `reboot`),
   löscht die Datei und führt `systemctl poweroff` bzw. `systemctl reboot` aus.

Der Container bleibt damit **unprivilegiert**.

## Einrichtung

Angenommen das Repo liegt unter `/home/pi/papermind` (sonst Pfade anpassen):

```bash
# 1) Geteiltes Verzeichnis anlegen (entspricht HOST_CONTROL_DIR / Compose-Default ./host-control)
mkdir -p /home/pi/papermind/host-control
chmod 0770 /home/pi/papermind/host-control

# 2) Watcher ausführbar machen
chmod +x /home/pi/papermind/deploy/host-control/papermind-host-control.sh

# 3) systemd-Service installieren (Pfade in der .service ggf. anpassen)
sudo cp /home/pi/papermind/deploy/host-control/papermind-host-control.service \
        /etc/systemd/system/papermind-host-control.service
sudo systemctl daemon-reload
sudo systemctl enable --now papermind-host-control.service

# Status prüfen
systemctl status papermind-host-control.service
```

In der `.env` (neben `docker-compose.prod.yml`) kann der Host-Pfad gesetzt
werden, falls er vom Standard `./host-control` abweicht:

```dotenv
HOST_CONTROL_DIR=/home/pi/papermind/host-control
```

`CONTROL_DIR` in der `.service` muss auf **dasselbe** Verzeichnis zeigen.

## Test

```bash
echo "reboot" > /home/pi/papermind/host-control/command   # -> Pi startet neu
journalctl -u papermind-host-control.service -f           # Logs mitlesen
```

Ohne eingerichteten Helfer funktioniert die Status-Anzeige (CPU, RAM,
Temperatur, Lüfter, Speicher) trotzdem – nur die Power-Buttons sind dann
deaktiviert.
