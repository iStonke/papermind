#!/usr/bin/env python3
"""Client for the local, allow-listed PaperMind Pi bridge."""

from __future__ import annotations

import json
import socket
import sys

SOCKET_PATH = "/tmp/papermind-pi-bridge.sock"
VALID_ACTIONS = {"status", "restore_drill", "recovery_check"}


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
