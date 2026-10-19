#!/usr/bin/env python3
"""Client for the local, allow-listed PaperMind Pi bridge."""

from __future__ import annotations

import json
import socket
import sys

SOCKET_PATH = "/tmp/papermind-pi-bridge.sock"
VALID_ACTIONS = {
    "status",
    "scanner_status",
    "scanner_calibration_test",
    "scanner_calibration_restore",
    "scanner_timing_test",
    "scanner_timing_restore",
    "scanner_jpeg_test",
    "scanner_jpeg_restore",
    "scanner_poller_restart",
    "restore_drill",
    "recovery_check",
    "quiet_fan_profile",
    "rollout",
    "rollout_status",
    "rollout_verify",
    "git_reconcile_status",
    "git_reconcile",
    "performance_audit",
    "performance_audit_status",
    "security_inventory",
    "security_patch_inspect",
    "security_patch_prepare",
    "security_patch_rollout",
    "security_patch_status",
    "security_patch_inventory",
    "security_patch_verify",
    "security_patch_measure",
    "security_patch_measure_status",
    "security_patch_live_inventory",
    "security_patch_host_plan",
    "security_patch_host_apply",
    "security_patch_host_status",
    "security_patch_restart",
    "import_release_inspect",
    "import_release_prepare",
    "import_release_apply",
    "import_release_status",
    "import_release_verify",
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_ACTIONS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(sorted(VALID_ACTIONS))}>", file=sys.stderr)
        return 2

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps({"action": sys.argv[1]}).encode("utf-8"))
        chunks: list[bytes] = []
        while chunk := client.recv(65536):
            chunks.append(chunk)

    response = json.loads(b"".join(chunks).decode("utf-8"))
    if response.get("stdout"):
        print(response["stdout"], end="")
    if response.get("stderr"):
        print(response["stderr"], end="", file=sys.stderr)
    return int(response.get("returncode", 1))


if __name__ == "__main__":
    raise SystemExit(main())
