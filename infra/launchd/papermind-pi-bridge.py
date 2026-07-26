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


def run_action(action: str) -> dict[str, object]:
    command, timeout = ACTIONS[action]
    try:
        result = subprocess.run(
            [*SSH_ARGS, command],
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
            "stdout": (exc.stdout or "")[-1_000_000:],
            "stderr": ((exc.stderr or "") + f"\nTimed out after {timeout} seconds.")[-100_000:],
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
        connection.sendall(json.dumps(response).encode("utf-8"))


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
