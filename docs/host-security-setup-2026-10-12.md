# Einmalige Freigabe der festen Host-Sicherheitsupdates

Der Pi verlangt für APT ein sudo-Passwort. Die Bridge überträgt keine Passwörter.
Die folgenden Befehle installieren den bereits geprüften Helfer als root-eigene
Datei und erlauben Jan ausschließlich fünf feste Aktionen dieses Releases.
Die sudoers-Regel prüft zusätzlich den SHA-256 des Helfers. Keine frei wählbaren
Pakete, Befehle, Pfade oder Umgebungsvariablen; kein Pi-Neustart. Der Helfer
erzeugt seinen Versionsplan selbst und speichert ihn ausschließlich unter root.

Auf dem Pi in einem eigenen Terminal ausführen:

```bash
cd ~/papermind
printf '%s\n' '729b298d38d1bc68a4a6e67ee9956e17cf9f140abb9c890e99475845e88727c8  .runtime/pi-security-patch/pi_host_security_root.py' | sha256sum -c
sudo install -D -o root -g root -m 0755 .runtime/pi-security-patch/pi_host_security_root.py /usr/local/libexec/papermind-security-20261012
sudo visudo -cf .runtime/pi-security-patch/pi_host_security_sudoers && sudo install -o root -g root -m 0440 .runtime/pi-security-patch/pi_host_security_sudoers /etc/sudoers.d/papermind-security-20261012
```

Nur fortfahren, wenn die Prüfsumme und `visudo` erfolgreich sind. Das Passwort
wird gegebenenfalls ausschließlich im Pi-Terminal eingegeben. Diese Befehle
installieren noch keine Pakete. Danach kann die Bridge den festen Plan erstellen,
prüfen, herunterladen und nach Sicherung anwenden.

Nach Abschluss lässt sich die temporäre Freigabe durch Entfernen der Datei
`/etc/sudoers.d/papermind-security-20261012` zurücknehmen. Der Helfer liegt unter
`/usr/local/libexec/papermind-security-20261012`, sein privater Plan unter
`/var/lib/papermind-security-20261012`.
