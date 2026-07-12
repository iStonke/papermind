#!/usr/bin/env bash
# Keep the directly attached USB scanner out of Linux runtime autosuspend.
#
# The scan button poller opens and closes the pixma device for every button read.
# After longer idle periods, runtime autosuspend can add a noticeable wake-up
# delay before the first read/scan. This script is intentionally idempotent and
# safe to run at boot and on USB add/change events.
set -uo pipefail

SCANNER_USB_VENDOR="${SCANNER_USB_VENDOR:-04a9}"
SCANNER_USB_PRODUCT="${SCANNER_USB_PRODUCT:-}"

log() {
  echo "[papermind-scanner-usb-awake] $*"
  command -v logger >/dev/null 2>&1 && logger -t papermind-scanner-usb-awake -- "$*" || true
}

lower() {
  tr '[:upper:]' '[:lower:]'
}

write_sysfs() {
  local path="$1"
  local value="$2"
  [ -w "$path" ] || return 1
  printf '%s\n' "$value" >"$path" 2>/dev/null
}

vendor_filter="$(printf '%s' "$SCANNER_USB_VENDOR" | lower)"
product_filter="$(printf '%s' "$SCANNER_USB_PRODUCT" | lower)"
found=0

for dev in /sys/bus/usb/devices/*; do
  [ -r "${dev}/idVendor" ] || continue

  vendor="$(lower <"${dev}/idVendor")"
  product=""
  [ -r "${dev}/idProduct" ] && product="$(lower <"${dev}/idProduct")"

  [ "$vendor" = "$vendor_filter" ] || continue
  if [ -n "$product_filter" ] && [ "$product" != "$product_filter" ]; then
    continue
  fi

  found=1
  write_sysfs "${dev}/power/control" "on" || log "Kann ${dev}/power/control nicht schreiben"
  write_sysfs "${dev}/power/autosuspend_delay_ms" "-1" || true
  write_sysfs "${dev}/power/autosuspend" "-1" || true

  control="$(cat "${dev}/power/control" 2>/dev/null || printf '?')"
  delay="$(cat "${dev}/power/autosuspend_delay_ms" 2>/dev/null || cat "${dev}/power/autosuspend" 2>/dev/null || printf '?')"
  log "USB ${dev##*/} idVendor=${vendor} idProduct=${product:-?} power/control=${control} autosuspend=${delay}"
done

if [ "$found" -eq 0 ]; then
  log "Kein USB-Geraet mit idVendor=${vendor_filter}${product_filter:+ idProduct=${product_filter}} gefunden"
fi

exit 0
