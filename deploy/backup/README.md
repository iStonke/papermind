# PaperMind-Backup-Härtung

Neue Sicherungen bestehen aus einem Datenbank-Dump, dem Dokumentenspeicher und
einem signierten Manifest mit Version, Tabellenzählern, Metadaten-Fingerprint
und SHA-256-Prüfsummen. Die Artefakte werden mit AES-256-GCM verschlüsselt und
erst nach erfolgreicher Gegenprüfung auf dem NAS atomar veröffentlicht.

## Verschlüsselungsschlüssel

`scripts/deploy_pi.sh --prod` erzeugt beim ersten Lauf automatisch
`.runtime/secrets/backup.key` (Modus 0600). Die Datei wird read-only in Backend
und Worker eingebunden und danach nicht mehr verändert.

Die Schlüsseldatei muss zusätzlich offline und getrennt von den Backups
aufbewahrt werden. Ohne sie lassen sich verschlüsselte Backups und in den
Einstellungen verschlüsselte NAS-Passwörter nicht wiederherstellen. Alternativ
kann ein externer Secret Store `BACKUP_ENCRYPTION_KEY` bereitstellen.

## Generationen und zweites Ziel

Die Oberfläche verwaltet getrennte tägliche, wöchentliche und monatliche
Generationen (GFS). Optional kann dort ein zweites SMB-Ziel aktiviert werden.
Ein Lauf gilt erst als erfolgreich, wenn Upload und Prüfsumme auf allen
aktivierten Zielen erfolgreich waren.

Fehler und ein zu altes letztes Backup können über
`BACKUP_ALERT_WEBHOOK_URL` an einen externen HTTP-Webhook gemeldet werden.

## Wiederherstellung

Vor einer produktiven Wiederherstellung werden Manifest, Prüfsummen,
Entschlüsselung, Storage-Referenzen und ein Restore in eine temporäre Datenbank
geprüft. Danach erzeugt PaperMind ein zusätzliches Sicherheitsbackup. Scheitert
das Einspielen oder die abschließende Metadatenprüfung, wird dieses automatisch
zurückgespielt.

## Automatischer Restore-Drill

Der Timer stellt am ersten Sonntag jedes Monats das neueste vollständige Backup
in isolierten Docker-Ressourcen wieder her. Produktive Daten werden nur gelesen.

Installation auf dem Pi:

```bash
sudo cp deploy/backup/papermind-restore-drill.service /etc/systemd/system/
sudo cp deploy/backup/papermind-restore-drill.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now papermind-restore-drill.timer
```

Das Ergebnis wird in PaperMind gespeichert und in den Backup-Einstellungen als
Zeitpunkt der zuletzt geprüften Wiederherstellung angezeigt. Fehler werden auch
an den konfigurierten Backup-Webhook gesendet.
