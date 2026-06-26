#!/usr/bin/env bash
# =============================================================================
#  PaperMind – Tasten-Poller für Canon LiDE 400 (pixma) – Ersatz für scanbd
#
#  Warum nicht scanbd? Bei pixma+LiDE 400 ist scanbd dreifach fragil: verrauschte
#  Buttonwerte (unzuverlässiges Triggern), Geräte-Konflikt (scanbd hält das
#  Gerät, das Action-Script will gleichzeitig scannen) und DBus-Policy.
#
#  Dieser Poller umgeht all das: EIN Prozess liest button-1/button-2 über
#  `scanimage -A` und scannt anschließend selbst – sequenziell, also nie ein
#  Konflikt ums Gerät. Bei steigender Flanke (0->1):
#     button-1 -> papermind-scan.sh page    (Seite an Batch anhängen)
#     button-2 -> papermind-scan.sh finish   (Batch als PDF abschließen)
#
#  Läuft als systemd-Dienst (papermind-scan-watch.service) als Benutzer jan.
#  WICHTIG: scanbd muss deaktiviert sein, sonst belegt es das Gerät.
#
#  Jeder Poll ist ein USB-Control-Transfer zum Scanner (open/close der
#  pixma-Session). Dauerhaft im Sekundenbruchteil-Takt zu pollen erzeugt
#  unnötige USB-Last auf dem Pi. Daher adaptives Intervall: kurz nach einer
#  Tastenaktion wird schnell gepollt (flüssiges Mehrseiten-Scannen), nach
#  ACTIVE_WINDOW_SECONDS Ruhe ohne weitere Taste fällt der Poller auf das
#  seltenere Ruhe-Intervall zurück – das ist der Normalfall über den Tag.
#
#  Konfiguration über Environment:
#    SCAN_DEVICE            SANE-Device (leer = pixma-Scanner automatisch suchen)
#    ACTIVE_POLL_INTERVAL   Sekunden zwischen Abfragen kurz nach einer Taste (Default 0.7)
#    IDLE_POLL_INTERVAL     Sekunden zwischen Abfragen in Ruhe (Default 3)
#    ACTIVE_WINDOW_SECONDS  Wie lange nach einer Taste das schnelle Intervall gilt (Default 10)
# =============================================================================

# Bewusst KEIN `set -e`: Ein einzelner Lesefehler darf den Daemon nicht beenden.
set -uo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SCAN_SCRIPT="${_SCRIPT_DIR}/papermind-scan.sh"
ACTIVE_POLL_INTERVAL="${ACTIVE_POLL_INTERVAL:-0.7}"
IDLE_POLL_INTERVAL="${IDLE_POLL_INTERVAL:-3}"
ACTIVE_WINDOW_SECONDS="${ACTIVE_WINDOW_SECONDS:-10}"

log() {
  echo "[papermind-scan-watch] $*"
  command -v logger >/dev/null 2>&1 && logger -t papermind-scan-watch -- "$*" || true
}

detect_device() {
  # scanimage -L: device `pixma:04A91912_50F25C' is a ...
  scanimage -L 2>/dev/null | grep -oE "pixma:[^']+" | head -n1
}

# button-1/button-2 in EINEM scanimage-Aufruf lesen. Gibt "b1 b2" zurück,
# bei Lesefehler "x x" (z. B. Gerät gerade belegt/abgezogen).
read_buttons() {
  local out b1 b2
  out="$(scanimage -d "$DEV" -A 2>/dev/null)" || { echo "x x"; return; }
  [ -n "$out" ] || { echo "x x"; return; }
  # Erster numerischer [..]-Wert hinter der Option ist der Zustand; [read-only]
  # enthält Buchstaben und wird vom Muster [0-9-] nicht getroffen.
  b1="$(printf '%s\n' "$out" | grep -E -- '--button-1' | grep -oE '\[[0-9-]+\]' | head -n1 | tr -d '[]')"
  b2="$(printf '%s\n' "$out" | grep -E -- '--button-2' | grep -oE '\[[0-9-]+\]' | head -n1 | tr -d '[]')"
  echo "${b1:-x} ${b2:-x}"
}

DEV="${SCAN_DEVICE:-}"
[ -n "$DEV" ] || DEV="$(detect_device)"
export SCAN_DEVICE="$DEV"

log "Poller gestartet (Gerät: ${DEV:-suche…}, aktiv ${ACTIVE_POLL_INTERVAL}s / Ruhe ${IDLE_POLL_INTERVAL}s). button-1→page, button-2→finish."

# Sekunden-Timestamp der letzten Tastenaktion; 0 = noch keine -> sofort Ruhe-Intervall.
last_activity=0

current_interval() {
  local now=$EPOCHSECONDS
  if [ "$last_activity" != 0 ] && (( now - last_activity < ACTIVE_WINDOW_SECONDS )); then
    echo "$ACTIVE_POLL_INTERVAL"
  else
    echo "$IDLE_POLL_INTERVAL"
  fi
}

last1=0
last2=0
while true; do
  if [ -z "$DEV" ]; then
    DEV="$(detect_device)"
    export SCAN_DEVICE="$DEV"
    [ -n "$DEV" ] && log "Scanner gefunden: $DEV"
    sleep "$(current_interval)"
    continue
  fi

  read -r b1 b2 <<<"$(read_buttons)"

  # Lesefehler: nicht als Tastendruck werten, Zustand nicht verändern.
  if [ "$b1" = x ] || [ "$b2" = x ]; then
    sleep "$(current_interval)"
    continue
  fi

  if [ "$b1" = 1 ] && [ "$last1" != 1 ]; then
    log "button-1 → Seite scannen"
    last_activity=$EPOCHSECONDS
    "$SCAN_SCRIPT" page || log "page fehlgeschlagen"
  fi
  if [ "$b2" = 1 ] && [ "$last2" != 1 ]; then
    log "button-2 → Batch abschließen"
    last_activity=$EPOCHSECONDS
    "$SCAN_SCRIPT" finish || log "finish fehlgeschlagen"
  fi

  last1="$b1"
  last2="$b2"
  sleep "$(current_interval)"
done
