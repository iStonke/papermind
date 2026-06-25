#!/usr/bin/env bash
# =============================================================================
#  PaperMind – Flachbett-Scan über Hardware-Tasten (Canon LiDE 400)
#
#  Der Scanner hängt per USB am HOST (Pi), nicht im unprivilegierten Container.
#  Dieses Script läuft daher auf dem HOST und wird von ``scanbd`` aufgerufen,
#  wenn eine der 5 Scan-Tasten gedrückt wird (siehe scanbd-papermind.conf).
#
#  Es schreibt das fertige PDF in den bestehenden Drop-Ordner ``scan-inbox``.
#  Ab da übernimmt der ganz normale PaperMind-Weg (identisch zur SMB-Aktion):
#    Worker erkennt stabile PDF -> ImportInboxService -> Import-Inbox -> Badge.
#  Es ist also KEIN Backend-/Frontend-Code nötig – der Scanner ist nur ein
#  weiterer PDF-Produzent für scan-inbox.
#
#  Flachbett hat keinen Einzug -> ein Tastendruck = eine Seite. Mehrseitige
#  Dokumente werden als "Batch" gesammelt und mit einer zweiten Taste (oder per
#  Idle-Timeout) zu einer mehrseitigen PDF abgeschlossen.
#
#  Unterbefehle:
#    page          Eine Seite scannen und an den laufenden Batch anhängen.
#    finish        Laufenden Batch zu einer PDF abschließen -> scan-inbox.
#    finalize-idle Batch nur abschließen, wenn er seit IDLE_SECONDS ruht
#                  (Sicherheitsnetz, von einem systemd-Timer aufgerufen).
#    status        Aktuellen Batch-Stand ausgeben (Debug).
#
#  Konfiguration über Environment (Defaults für /home/pi/papermind):
#    SCAN_INBOX_DIR   Ziel-Drop-Ordner (== Host-Mount von /scan-inbox)
#    SCAN_DEVICE      SANE-Device (leer = Default-Scanner)
#    SCAN_RESOLUTION  DPI (Default 300)
#    SCAN_MODE        Color | Gray | Lineart (Default Color)
#    IDLE_SECONDS     Ruhezeit für finalize-idle (Default 180)
# =============================================================================

set -euo pipefail

SCAN_INBOX_DIR="${SCAN_INBOX_DIR:-/home/pi/papermind/scan-inbox}"
# Batch-Ablage als Dot-Verzeichnis IM Drop-Ordner: Der Worker ignoriert
# Dateien/Ordner mit führendem Punkt, sieht also nur die fertige PDF.
BATCH_DIR="${BATCH_DIR:-${SCAN_INBOX_DIR}/.papermind-batch}"
LOCK_FILE="${LOCK_FILE:-${SCAN_INBOX_DIR}/.papermind-scan.lock}"

SCAN_DEVICE="${SCAN_DEVICE:-}"
SCAN_RESOLUTION="${SCAN_RESOLUTION:-300}"
SCAN_MODE="${SCAN_MODE:-Color}"
IDLE_SECONDS="${IDLE_SECONDS:-180}"

log() { echo "[papermind-scan] $*"; }
die() { log "FEHLER: $*"; exit 1; }

_require() { command -v "$1" >/dev/null 2>&1 || die "Benötigtes Programm fehlt: $1"; }

# Alle device-berührenden Aktionen serialisieren – zwei schnelle Tastendrücke
# dürfen sich nicht überlappen (Scanner erlaubt nur einen Zugriff).
_with_lock() {
  exec 9>"$LOCK_FILE"
  flock 9
}

_scan_args() {
  # Gemeinsame scanimage-Argumente. --device nur setzen, wenn vorgegeben.
  local -a args=()
  [[ -n "$SCAN_DEVICE" ]] && args+=(--device-name "$SCAN_DEVICE")
  args+=(--resolution "$SCAN_RESOLUTION" --mode "$SCAN_MODE" --format=png)
  printf '%s\n' "${args[@]}"
}

cmd_page() {
  _require scanimage
  _with_lock
  mkdir -p "$BATCH_DIR"

  # Nächsten, nullgepolsterten Seitenindex bestimmen.
  local next
  next="$(find "$BATCH_DIR" -maxdepth 1 -name 'page-*.png' -printf '.' 2>/dev/null | wc -c)"
  next=$((next + 1))
  local idx
  idx="$(printf '%03d' "$next")"

  local part="${BATCH_DIR}/page-${idx}.png.part"
  local final="${BATCH_DIR}/page-${idx}.png"

  log "Scanne Seite ${idx} (${SCAN_RESOLUTION}dpi ${SCAN_MODE})…"
  # shellcheck disable=SC2046
  if ! scanimage $(_scan_args) > "$part"; then
    rm -f "$part"
    die "scanimage fehlgeschlagen (Device frei? Deckel zu? 'scanimage -L' prüfen)"
  fi
  [[ -s "$part" ]] || { rm -f "$part"; die "Leeres Scan-Ergebnis"; }
  mv -f "$part" "$final"
  log "Seite ${idx} gespeichert. Batch enthält jetzt ${next} Seite(n)."
}

_finalize() {
  # Setzt den Lock voraus.
  shopt -s nullglob
  local pages=("$BATCH_DIR"/page-*.png)
  shopt -u nullglob
  if (( ${#pages[@]} == 0 )); then
    log "Kein offener Batch – nichts abzuschließen."
    return 0
  fi

  local ts incoming target
  ts="$(date +%Y%m%d-%H%M%S)"
  # Erst als Dot-Tempdatei schreiben, dann atomar umbenennen, damit der Worker
  # niemals eine halbfertige PDF sieht (er wartet zusätzlich auf Datei-Ruhe).
  incoming="${SCAN_INBOX_DIR}/.incoming-${ts}.pdf"
  target="${SCAN_INBOX_DIR}/Scan-${ts}.pdf"

  log "Schließe Batch mit ${#pages[@]} Seite(n) zu ${target##*/} ab…"
  if command -v img2pdf >/dev/null 2>&1; then
    img2pdf --output "$incoming" "${pages[@]}"
  elif command -v convert >/dev/null 2>&1; then
    convert "${pages[@]}" "$incoming"   # ImageMagick-Fallback
  else
    die "Weder img2pdf noch ImageMagick (convert) installiert"
  fi

  mv -f "$incoming" "$target"
  rm -f "$BATCH_DIR"/page-*.png
  log "Fertig: ${target} – erscheint gleich im Importscreen."
}

cmd_finish() {
  # PDF-Werkzeug wird in _finalize geprüft (img2pdf bevorzugt, sonst convert).
  _with_lock
  _finalize
}

cmd_finalize_idle() {
  _with_lock
  shopt -s nullglob
  local pages=("$BATCH_DIR"/page-*.png)
  shopt -u nullglob
  (( ${#pages[@]} == 0 )) && { log "Kein offener Batch."; return 0; }

  # Jüngste Seite ermitteln; nur abschließen, wenn lange genug Ruhe herrscht.
  local newest age now
  newest="$(stat -c %Y "${pages[@]}" | sort -nr | head -n1)"
  now="$(date +%s)"
  age=$((now - newest))
  if (( age < IDLE_SECONDS )); then
    log "Batch noch aktiv (${age}s < ${IDLE_SECONDS}s) – warte."
    return 0
  fi
  log "Batch seit ${age}s ruhig – schließe automatisch ab."
  _finalize
}

cmd_status() {
  shopt -s nullglob
  local pages=("$BATCH_DIR"/page-*.png)
  shopt -u nullglob
  log "Offener Batch: ${#pages[@]} Seite(n) in ${BATCH_DIR}"
}

main() {
  mkdir -p "$SCAN_INBOX_DIR"
  case "${1:-}" in
    page)           cmd_page ;;
    finish)         cmd_finish ;;
    finalize-idle)  cmd_finalize_idle ;;
    status)         cmd_status ;;
    *) die "Unbekannter Unterbefehl '${1:-}'. Erlaubt: page | finish | finalize-idle | status" ;;
  esac
}

main "$@"
