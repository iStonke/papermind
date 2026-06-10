#!/usr/bin/env bash
# =============================================================================
#  PaperMind – Host-Control Watcher
#
#  Der Backend-Container kann den Raspberry Pi nicht selbst herunterfahren oder
#  neu starten. Statt dessen schreibt das Backend eine Kommando-Datei in ein
#  geteiltes Verzeichnis (HOST_CONTROL_DIR). Dieses Script läuft auf dem HOST
#  (als systemd-Service, siehe papermind-host-control.service), überwacht das
#  Verzeichnis und führt die angeforderte Aktion aus.
#
#  Erlaubte Kommandos (erstes Wort der Datei): poweroff | reboot
#
#  Verwendung:
#    CONTROL_DIR=/home/pi/papermind/host-control ./papermind-host-control.sh
# =============================================================================

set -euo pipefail

CONTROL_DIR="${CONTROL_DIR:-/home/pi/papermind/host-control}"
COMMAND_FILE="${CONTROL_DIR}/command"
POLL_INTERVAL="${POLL_INTERVAL:-3}"

log() { echo "[papermind-host-control] $*"; }

mkdir -p "$CONTROL_DIR"
# Container schreibt als root – Verzeichnis muss von beiden Seiten beschreibbar sein.
chmod 0770 "$CONTROL_DIR" 2>/dev/null || true

log "Überwache ${COMMAND_FILE} (Intervall ${POLL_INTERVAL}s)"

while true; do
  if [[ -f "$COMMAND_FILE" ]]; then
    action="$(head -n1 "$COMMAND_FILE" 2>/dev/null | awk '{print $1}')"
    rm -f "$COMMAND_FILE" 2>/dev/null || true

    case "$action" in
      poweroff)
        log "Kommando empfangen: poweroff – fahre Host herunter"
        sync
        systemctl poweroff
        ;;
      reboot)
        log "Kommando empfangen: reboot – starte Host neu"
        sync
        systemctl reboot
        ;;
      "")
        : # leere Datei, ignorieren
        ;;
      *)
        log "Unbekanntes Kommando ignoriert: '${action}'"
        ;;
    esac
  fi
  sleep "$POLL_INTERVAL"
done
