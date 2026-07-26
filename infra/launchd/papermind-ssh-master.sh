#!/bin/sh
# Wird von com.papermind.ssh-tunnel.launchd im Benutzerkontext gestartet.
# Ein ControlMaster mit ControlPersist bleibt nach dem kurzen Bootstrap-Befehl
# aktiv und kann dadurch Pi-Kommandos über denselben authentifizierten Kanal
# ausführen. Der Loop beendet sich bei Verbindungsverlust; launchd startet ihn
# dann wieder.
set -eu

socket_path=/tmp/papermind-ssh-control.sock
remote=jan@192.168.178.92

rm -f "${socket_path}"

/usr/bin/ssh \
  -M \
  -S "${socket_path}" \
  -o ControlPersist=300 \
  -i /Users/admin/.ssh/id_rsa \
  -o HostKeyAlias=papermind-pi-lan \
  -o StrictHostKeyChecking=accept-new \
  -o BatchMode=yes \
  -o ExitOnForwardFailure=yes \
  -o ConnectTimeout=15 \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o TCPKeepAlive=yes \
  -L 127.0.0.1:2222:192.168.178.92:22 \
  -f "${remote}" true

while /usr/bin/ssh -S "${socket_path}" -O check "${remote}" >/dev/null 2>&1; do
  sleep 15
done

exit 1
