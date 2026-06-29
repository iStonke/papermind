#!/usr/bin/env bash
# =============================================================================
#  PaperMind – Flachbett-Scan über Hardware-Tasten (Canon LiDE 400)
#
#  Der Scanner hängt per USB am HOST (Pi), nicht im unprivilegierten Container.
#  Dieses Script läuft daher auf dem HOST und wird vom Tasten-Poller
#  ``papermind-scan-watch.sh`` aufgerufen, wenn eine Scan-Taste gedrückt wird.
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
#  Optionaler Live-Modus (pro Scanner in den Scanner-Einstellungen der App):
#  Statt zu sammeln wird jede Seite SOFORT als eigene 1-Seiten-PDF nach
#  scan-inbox/ gelegt. Das Frontend gruppiert mehrere kurz hintereinander
#  eintreffende Seiten im offenen Importfenster zu einem Dokument - button-2
#  wird dann nicht mehr benötigt. Der Worker spiegelt die Einstellung in
#  ``${SCAN_INBOX_DIR}/.papermind-scanner-config`` (siehe worker/main.py,
#  _sync_scanner_live_mode_config); dieses Script liest nur diese Datei.
#
#  Unterbefehle:
#    page          Eine Seite scannen und an den laufenden Batch anhängen.
#    finish        Laufenden Batch zu einer PDF abschließen -> scan-inbox.
#    finalize-idle Batch nur abschließen, wenn er seit IDLE_SECONDS ruht
#                  (Sicherheitsnetz, von einem systemd-Timer aufgerufen).
#    status        Aktuellen Batch-Stand ausgeben (Debug).
#
#  Konfiguration über Environment:
#    SCAN_INBOX_DIR   Ziel-Drop-Ordner (Default: aus Repo-Pfad abgeleitet)
#    SCAN_DEVICE      SANE-Device (leer = Default-Scanner)
#    SCAN_RESOLUTION  DPI (Default 300)
#    SCAN_MODE        Color | Gray | Lineart (Default Color)
#    IDLE_SECONDS     Ruhezeit für finalize-idle (Default 180)
# =============================================================================

set -euo pipefail

# scan-inbox wird standardmäßig aus dem eigenen Repo-Pfad abgeleitet
# (<repo>/deploy/scan-button/ -> <repo>/scan-inbox), damit der Pfad nicht vom
# Benutzernamen abhängt. Per SCAN_INBOX_DIR override-bar.
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
_REPO_ROOT="$(cd "${_SCRIPT_DIR}/../.." && pwd)"
SCAN_INBOX_DIR="${SCAN_INBOX_DIR:-${_REPO_ROOT}/scan-inbox}"
# Batch-Ablage als Dot-Verzeichnis IM Drop-Ordner: Der Worker ignoriert
# Dateien/Ordner mit führendem Punkt, sieht also nur die fertige PDF.
BATCH_DIR="${BATCH_DIR:-${SCAN_INBOX_DIR}/.papermind-batch}"
LOCK_FILE="${LOCK_FILE:-${SCAN_INBOX_DIR}/.papermind-scan.lock}"

# Gerät: SCAN_DEVICE wird vom Poller (papermind-scan-watch.sh) exportiert;
# leer = SANE-Default-Scanner.
SCAN_DEVICE="${SCAN_DEVICE:-}"
SCAN_RESOLUTION="${SCAN_RESOLUTION:-300}"
SCAN_MODE="${SCAN_MODE:-Color}"
IDLE_SECONDS="${IDLE_SECONDS:-180}"
# Optionale Backend-Job-ID (vom Poller bei UI-ausgelösten Scans gesetzt). Wird in
# den PDF-Dateinamen eingebettet, damit das Backend den Lauf exakt diesem Job
# zuordnen kann. Leer bei Hardware-Tasten / Idle-Finalisierung.
PAPERMIND_SCAN_JOB_ID="${PAPERMIND_SCAN_JOB_ID:-}"

# Ausgabe sowohl auf stdout (manueller Aufruf) als auch nach syslog – Letzteres,
# damit man bei tastengesteuerten Läufen (scanbd verschluckt stdout) in
# `journalctl -t papermind-scan` sieht, was passiert ist.
log() {
  echo "[papermind-scan] $*"
  command -v logger >/dev/null 2>&1 && logger -t papermind-scan -- "$*" || true
}
die() { log "FEHLER: $*"; exit 1; }

_require() { command -v "$1" >/dev/null 2>&1 || die "Benötigtes Programm fehlt: $1"; }

# Eingebettete Job-ID für den PDF-Dateinamen: "__pmjob-<uuid>", sonst leer. Der
# Worker löst den Marker wieder heraus (bereinigt den Anzeigenamen) und ordnet
# den Scan exakt diesem Backend-Job zu.
_job_filename_suffix() {
  local id="${PAPERMIND_SCAN_JOB_ID:-}"
  if [[ "$id" =~ ^[0-9a-fA-F-]{36}$ ]]; then
    printf '__pmjob-%s' "$id"
  fi
}

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

# Vom Worker gespiegelte Einstellung lesen (kein jq nötig, einfaches key=value).
_live_page_mode_enabled() {
  local cfg="${SCAN_INBOX_DIR}/.papermind-scanner-config"
  [[ -f "$cfg" ]] && grep -q '^LIVE_PAGE_MODE=true$' "$cfg" 2>/dev/null
}

# Umgekehrte Richtung zu _live_page_mode_enabled: Status für den Worker
# schreiben, damit das Importfenster anzeigen kann, dass aktuell gescannt
# wird. Der Worker liest diese Datei nur, er schreibt sie nicht.
_write_scan_status() {
  local status_file="${SCAN_INBOX_DIR}/.papermind-scanner-status"
  if [[ "$1" == "true" ]]; then
    printf 'SCANNING=true\nSTARTED_AT=%s\n' "$(date +%s)" > "$status_file" 2>/dev/null || true
  else
    printf 'SCANNING=false\n' > "$status_file" 2>/dev/null || true
  fi
}

# Live-Modus: eine Seite scannen und SOFORT als eigene 1-Seiten-PDF nach
# scan-inbox legen - kein Batch, kein Warten auf button-2.
_scan_live_page() {
  local tmp_dir="${SCAN_INBOX_DIR}/.papermind-live-tmp"
  mkdir -p "$tmp_dir"

  local ts png_part png incoming target
  ts="$(date +%Y%m%d-%H%M%S-%N)"
  png_part="${tmp_dir}/page-${ts}.png.part"
  png="${tmp_dir}/page-${ts}.png"

  log "Scanne Seite live (${SCAN_RESOLUTION}dpi ${SCAN_MODE})…"
  # shellcheck disable=SC2046
  if ! scanimage $(_scan_args) > "$png_part"; then
    rm -f "$png_part"
    die "scanimage fehlgeschlagen (Device frei? Deckel zu? 'scanimage -L' prüfen)"
  fi
  [[ -s "$png_part" ]] || { rm -f "$png_part"; die "Leeres Scan-Ergebnis"; }
  mv -f "$png_part" "$png"

  incoming="${SCAN_INBOX_DIR}/.incoming-${ts}.pdf"
  target="${SCAN_INBOX_DIR}/Scan-${ts}$(_job_filename_suffix).pdf"
  if command -v img2pdf >/dev/null 2>&1; then
    img2pdf --output "$incoming" "$png"
  elif command -v convert >/dev/null 2>&1; then
    convert "$png" "$incoming"   # ImageMagick-Fallback
  else
    rm -f "$png"
    die "Weder img2pdf noch ImageMagick (convert) installiert"
  fi
  mv -f "$incoming" "$target"
  rm -f "$png"
  log "Seite live gesendet: ${target##*/}"
}

cmd_page() {
  _require scanimage
  _with_lock
  # Status für die gesamte Lebensdauer dieses Prozesses verwalten: egal ob
  # Live- oder Batch-Pfad gleich normal zurückkehrt oder scanimage weiter
  # unten per die()/exit 1 abbricht (z.B. USB-Disconnect) - der EXIT-Trap
  # setzt den Status garantiert wieder auf "false".
  trap '_write_scan_status false' EXIT
  _write_scan_status true

  if _live_page_mode_enabled; then
    _scan_live_page
    return
  fi

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
  target="${SCAN_INBOX_DIR}/Scan-${ts}$(_job_filename_suffix).pdf"

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
