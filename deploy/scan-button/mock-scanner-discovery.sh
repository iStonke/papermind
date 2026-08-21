#!/usr/bin/env bash
# DEV-ONLY: Lokaler Ersatz für den Pi-Host-Poller.
#
# Schreibt ein SANE-Geräteinventar in scan-inbox/.papermind-scanner-devices,
# das der Worker (alle 0,5 s, _sync_scanner_discovery) einliest. Dadurch tauchen
# die Geräte im Scanner-Einstellungspanel als "Verfügbar" auf, ohne dass echte
# Hardware am lokalen Rechner hängt.
#
# Hintergrund: Ein Scanner gilt nur als available, solange discovered_at < 45 s
# alt ist (siehe ScannerService._read). Der Worker frischt discovered_at nur bei
# GEÄNDERTER Datei-mtime auf – deshalb schreibt dieses Skript die Datei in einer
# Schleife neu (Standard: alle 20 s), bis es mit Strg-C beendet wird. Beim
# Beenden wird die Inventardatei entfernt, damit die Geräte sauber verschwinden.
#
# Voraussetzung: Worker-Container läuft und mountet ./scan-inbox -> /scan-inbox.
#
# Aufruf (aus dem Repo-Root):
#   deploy/scan-button/mock-scanner-discovery.sh              # zwei Beispielgeräte
#   REFRESH=10 deploy/scan-button/mock-scanner-discovery.sh   # schnelleres Refresh
#   SCAN_INBOX_DIR=/pfad/zu/scan-inbox deploy/scan-button/mock-scanner-discovery.sh
set -euo pipefail

INBOX="${SCAN_INBOX_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../scan-inbox" 2>/dev/null && pwd || echo ./scan-inbox)}"
INVENTORY="$INBOX/.papermind-scanner-devices"
REFRESH="${REFRESH:-20}"

# Geräteliste: je Zeile "uri<TAB>Anzeigename".
# Die URI darf KEINE Leerzeichen enthalten (der Parser verwirft solche Zeilen),
# der Anzeigename dahinter darf welche haben.
DEVICES=$(printf '%s\t%s\n%s\t%s\n' \
  'genesys:libusb:001:005'          'Canon CanoScan LiDE 400' \
  'escl:https://192.168.178.42:443' 'Brother ADS-1700W')

if [ ! -d "$INBOX" ]; then
  echo "scan-inbox nicht gefunden: $INBOX" >&2
  exit 1
fi

cleanup() {
  rm -f "$INVENTORY"
  echo ""
  echo "Inventar entfernt – Geräte verschwinden in <45 s aus der Liste."
}
trap cleanup EXIT INT TERM

echo "Schreibe Mock-Inventar nach $INVENTORY (Refresh alle ${REFRESH}s, Strg-C zum Stoppen):"
printf '%s\n' "$DEVICES"
while true; do
  printf '%s\n' "$DEVICES" > "$INVENTORY"
  sleep "$REFRESH"
done
