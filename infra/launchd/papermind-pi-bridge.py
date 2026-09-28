#!/usr/bin/env python3
"""Local, allow-listed bridge for PaperMind Pi operations.

The process is run by a macOS user LaunchAgent. It accepts one JSON request per
Unix-socket connection and runs only the commands defined in ACTIONS. No shell
command supplied by a client is ever evaluated.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path

SOCKET_PATH = Path("/tmp/papermind-pi-bridge.sock")
LOG_PATH = Path("/tmp/papermind-pi-bridge.log")
SCANNER_SCRIPT_SOURCE = Path(
    "/Users/admin/Library/Application Support/PaperMind/papermind-scan-timing.sh"
)
# Der Pi antwortet auf dem lokalen Netz zuverlässig über seinen IPv6/mDNS-Host.
# Die Mac-Bridge läuft außerhalb der Codex-Sandbox und kann diesen Transportweg
# nutzen; eine fest verdrahtete IPv4-Verbindung blieb nach dem SSH-Handshake
# hängen.
PI_TARGET = "jan@papermind"
SSH_ARGS = [
    "/usr/bin/ssh",
    # The Pi user environment is exercised through an interactive SSH shell in
    # normal administration. Force a PTY here as well so fixed maintenance
    # commands use the same supported execution path.
    "-tt",
    "-i",
    "/Users/admin/.ssh/id_rsa",
    "-o",
    "HostKeyAlias=papermind-pi-lan",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "ServerAliveInterval=30",
    "-o",
    "ServerAliveCountMax=3",
    PI_TARGET,
]

# Every bridge operation is intentionally fixed and auditable. Add an operation
# here instead of accepting caller-provided shell text.
ACTIONS: dict[str, tuple[str, int]] = {
    "status": (
        "cd /home/jan/papermind && "
        "git rev-parse --short HEAD && "
        "docker compose --env-file .env.prod -f docker-compose.prod.yml "
        "ps --format '{{.Service}} {{.Status}}'",
        60,
    ),
    "scanner_status": (
        "set -u; "
        "echo '=== scanner services ==='; "
        "systemctl show papermind-scanner-usb-awake.service papermind-scan-watch.service "
        "--property=Id,LoadState,ActiveState,SubState,Result,ExecMainStatus --no-pager 2>&1 || true; "
        "echo '=== scanner service definitions ==='; "
        "systemctl cat papermind-scanner-usb-awake.service papermind-scan-watch.service "
        "--no-pager 2>&1 || true; "
        "echo '=== Canon USB power ==='; "
        "found=0; "
        "for dev in /sys/bus/usb/devices/*; do "
        "test -r \"$dev/idVendor\" || continue; "
        "vendor=$(tr '[:upper:]' '[:lower:]' < \"$dev/idVendor\"); "
        "test \"$vendor\" = 04a9 || continue; "
        "found=1; "
        "printf '%s vendor=%s product=%s manufacturer=%s name=%s speed=%s power/control=%s autosuspend_delay_ms=%s runtime_status=%s\n' "
        "\"${dev##*/}\" \"$vendor\" "
        "\"$(cat \"$dev/idProduct\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/manufacturer\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/product\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/speed\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/power/control\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/power/autosuspend_delay_ms\" 2>/dev/null || printf '?')\" "
        "\"$(cat \"$dev/power/runtime_status\" 2>/dev/null || printf '?')\"; "
        "done; "
        "test \"$found\" = 1 || echo 'No Canon USB device found'; "
        "echo '=== SANE devices ==='; "
        "scanimage -V 2>&1 || true; "
        "sane_listing=$(scanimage -L 2>&1 || true); "
        "printf '%s\n' \"$sane_listing\"; "
        "echo '=== active scanner options ==='; "
        "scanner_device=$(printf '%s\n' \"$sane_listing\" | grep -oE \"pixma:[^']+\" | head -n1); "
        "printf 'inventory device=%s\n' \"${scanner_device:-missing}\"; "
        "test -z \"${scanner_device:-}\" || timeout 15 scanimage -d \"$scanner_device\" -A 2>&1 || true; "
        "echo '=== recent scanner journal ==='; "
        "journalctl -u papermind-scanner-usb-awake.service -u papermind-scan-watch.service "
        "--since '-6 hours' --no-pager -n 160 2>&1 || true; "
        "true",
        60,
    ),
    "scanner_calibration_test": (
        "set -eu; "
        "script=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${script}.papermind-calibration-test.bak; "
        "test -f \"$script\"; "
        "test -f \"$backup\" || cp --preserve=mode,timestamps \"$script\" \"$backup\"; "
        "grep -q '^SCAN_CALIBRATE=' \"$script\" || "
        "sed -i '/^SCAN_MODE=/a SCAN_CALIBRATE=\"${SCAN_CALIBRATE:-Once}\"' \"$script\"; "
        "grep -q -- '--calibrate \"$SCAN_CALIBRATE\"' \"$script\" || "
        "sed -i '/    --mode \"$SCAN_MODE\"/a\\    --calibrate \"$SCAN_CALIBRATE\"' \"$script\"; "
        "sed -i 's/^SCAN_CALIBRATE=.*/SCAN_CALIBRATE=\"${SCAN_CALIBRATE:-Never}\"/' \"$script\"; "
        "echo 'scanner calibration test active'; "
        "grep -n -E 'SCAN_CALIBRATE|--calibrate' \"$script\"; "
        "systemctl show papermind-scan-watch.service --property=ActiveState,SubState --no-pager",
        30,
    ),
    "scanner_calibration_restore": (
        "set -eu; "
        "script=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${script}.papermind-calibration-test.bak; "
        "test -f \"$backup\" && cp --preserve=mode,timestamps \"$backup\" \"$script\" || true; "
        "echo 'scanner calibration test restored'; "
        "grep -n -E 'SCAN_CALIBRATE|--calibrate' \"$script\" || true; "
        "systemctl show papermind-scan-watch.service --property=ActiveState,SubState --no-pager",
        30,
    ),
    "scanner_timing_test": (
        "set -eu; "
        "target=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${target}.papermind-timing-test.bak; "
        "incoming=${target}.papermind-timing-test.part; "
        "test -f \"$target\"; "
        "test -f \"$backup\" || cp --preserve=mode,timestamps \"$target\" \"$backup\"; "
        "cat >\"$incoming\"; "
        "chmod --reference=\"$target\" \"$incoming\"; "
        "bash -n \"$incoming\"; "
        "mv -f \"$incoming\" \"$target\"; "
        "echo 'scanner timing test active'; "
        "grep -n -E 'Phase Scanneraufnahme|Phase PDF-Erzeugung|Phase Vorschau' \"$target\"",
        30,
    ),
    "scanner_timing_restore": (
        "set -eu; "
        "target=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${target}.papermind-timing-test.bak; "
        "test -f \"$backup\"; "
        "cp --preserve=mode,timestamps \"$backup\" \"$target\"; "
        "echo 'scanner timing test restored'",
        30,
    ),
    "scanner_jpeg_test": (
        "set -eu; "
        "target=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${target}.papermind-jpeg-test.bak; "
        "test -f \"$target\"; "
        "grep -q '^SCAN_FORMAT=' \"$target\"; "
        "grep -q -- '--format=\"$SCAN_FORMAT\"' \"$target\"; "
        "test -f \"$backup\" || cp --preserve=mode,timestamps \"$target\" \"$backup\"; "
        "sed -i 's/^SCAN_FORMAT=.*/SCAN_FORMAT=\"${SCAN_FORMAT:-jpeg}\"/' \"$target\"; "
        "echo 'scanner JPEG test active'; "
        "grep -n -E 'SCAN_FORMAT|--format=' \"$target\"",
        30,
    ),
    "scanner_jpeg_restore": (
        "set -eu; "
        "target=/home/jan/papermind/deploy/scan-button/papermind-scan.sh; "
        "backup=${target}.papermind-jpeg-test.bak; "
        "test -f \"$backup\"; "
        "cp --preserve=mode,timestamps \"$backup\" \"$target\"; "
        "echo 'scanner JPEG test restored'",
        30,
    ),
    "restore_drill": (
        "cd /home/jan/papermind && "
        "./scripts/prod_pi_restore_drill.sh --confirm-production",
        3600,
    ),
    "recovery_check": (
        "cd /home/jan/papermind && "
        "./scripts/prod_pi_recovery_check.sh --confirm-production",
        900,
    ),
    "quiet_fan_profile": (
        "set -eu; "
        "cfg=/boot/firmware/config.txt; "
        "sudo test -f \"$cfg\"; "
        "sudo cp --preserve=mode,timestamps \"$cfg\" \"$cfg.papermind-fan.bak\"; "
        "sudo sed -i '/^# BEGIN PaperMind quiet fan profile$/, /^# END PaperMind quiet fan profile$/d' \"$cfg\"; "
        "sudo tee -a \"$cfg\" >/dev/null <<'EOF'\n"
        "\n# BEGIN PaperMind quiet fan profile\n"
        "# Pi 5: quiet in normal operation; full cooling remains available at 80 C.\n"
        "dtparam=fan_temp0=60000\n"
        "dtparam=fan_temp0_hyst=5000\n"
        "dtparam=fan_temp0_speed=55\n"
        "dtparam=fan_temp1=70000\n"
        "dtparam=fan_temp1_hyst=5000\n"
        "dtparam=fan_temp1_speed=75\n"
        "dtparam=fan_temp2=77500\n"
        "dtparam=fan_temp2_hyst=5000\n"
        "dtparam=fan_temp2_speed=110\n"
        "dtparam=fan_temp3=80000\n"
        "dtparam=fan_temp3_hyst=5000\n"
        "dtparam=fan_temp3_speed=250\n"
        "# END PaperMind quiet fan profile\n"
        "EOF\n"
        "sudo sed -n '/^# BEGIN PaperMind quiet fan profile$/, /^# END PaperMind quiet fan profile$/p' \"$cfg\"; "
        "echo 'Profile saved; reboot required before activation.'",
        60,
    ),
}

ACTION_INPUT_PATHS: dict[str, Path] = {
    "scanner_timing_test": SCANNER_SCRIPT_SOURCE,
}


def configure_logging() -> None:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def remove_stale_socket() -> None:
    try:
        info = SOCKET_PATH.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError(f"Refusing to replace unexpected socket path: {SOCKET_PATH}")
    SOCKET_PATH.unlink()


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_action(action: str) -> dict[str, object]:
    command, timeout = ACTIONS[action]
    action_input = None
    ssh_args = SSH_ARGS
    input_path = ACTION_INPUT_PATHS.get(action)
    if input_path is not None:
        action_input = input_path.read_text(encoding="utf-8")
        # A PTY does not reliably deliver EOF for piped file content. Only the
        # fixed file-transfer action uses a non-interactive SSH channel.
        ssh_args = [SSH_ARGS[0], "-T", *SSH_ARGS[2:]]
    try:
        result = subprocess.run(
            [*ssh_args, command],
            input=action_input,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        logging.info("action=%s returncode=%s", action, result.returncode)
        if result.returncode != 0:
            # Predefined maintenance actions do not print credentials. Keep a
            # bounded diagnostic tail so a disconnected local client never
            # hides a Pi-side failure.
            logging.error(
                "action=%s failed stdout_tail=%r stderr_tail=%r",
                action,
                result.stdout[-20_000:],
                result.stderr[-20_000:],
            )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-1_000_000:],
            "stderr": result.stderr[-100_000:],
        }
    except subprocess.TimeoutExpired as exc:
        logging.warning("action=%s timed_out=%s", action, timeout)
        return {
            "ok": False,
            "returncode": 124,
            "stdout": _coerce_text(exc.stdout)[-1_000_000:],
            "stderr": (_coerce_text(exc.stderr) + f"\nTimed out after {timeout} seconds.")[-100_000:],
        }


def handle_connection(connection: socket.socket) -> None:
    with connection:
        raw = connection.recv(4096)
        try:
            request = json.loads(raw.decode("utf-8"))
            action = request.get("action")
            if not isinstance(action, str) or action not in ACTIONS:
                raise ValueError("Unsupported bridge action")
            response = run_action(action)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            response = {"ok": False, "returncode": 2, "stdout": "", "stderr": str(exc)}
        try:
            connection.sendall(json.dumps(response).encode("utf-8"))
        except BrokenPipeError:
            logging.info("client disconnected before response was sent")


def main() -> int:
    configure_logging()
    remove_stale_socket()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(SOCKET_PATH))
        os.chmod(SOCKET_PATH, 0o600)
        server.listen(1)
        logging.info("bridge started pid=%s", os.getpid())
        while True:
            connection, _ = server.accept()
            handle_connection(connection)
    finally:
        server.close()
        try:
            SOCKET_PATH.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.exit(main())
