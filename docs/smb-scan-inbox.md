# SMB Scan-Inbox

PaperMind kann einen lokalen Ordner als Scan-Eingang überwachen. Wenn dieser Ordner per SMB freigegeben ist, kann die iOS Dateien-App direkt mit der nativen Funktion **Dokumente scannen** dorthin speichern.

## Alltag auf dem iPhone

1. Dateien-App öffnen.
2. SMB-Ort **PaperMind Scans** öffnen.
3. Menü **...** öffnen.
4. **Dokumente scannen** wählen.
5. Seiten scannen und **Sichern**.
6. In PaperMind erscheint am Button **Importieren** eine Badge.
7. **Importieren** -> **Neue Scans anzeigen** öffnen.

## Technischer Ablauf

Der Docker-Worker überwacht den Host-Ordner `./scan-inbox`, der im Container als `/scan-inbox` gemountet ist.

```text
scan-inbox/
  *.pdf                  # iOS legt neue Scans hier ab
  .papermind-processing/ # temporäre Verarbeitung
  .papermind-processed/  # erfolgreich übernommene Originale
  .papermind-failed/     # ungültige oder nicht lesbare PDFs
```

Neue PDFs werden erst verarbeitet, wenn sie einige Sekunden unverändert sind. Danach übernimmt PaperMind sie in das bestehende Import-Staging und erzeugt einen Eintrag in der Import-Inbox. Es wird nichts automatisch importiert.

## Konfiguration

In `.env`:

```env
IMPORT_INBOX_DROP_PATH=/scan-inbox
IMPORT_INBOX_FILE_STABLE_SECONDS=3
```

In `docker-compose.yml` wird der Host-Ordner so gemountet:

```yaml
./scan-inbox:${IMPORT_INBOX_DROP_PATH:-/scan-inbox}
```

## Raspberry Pi Setup

`scripts/setup_pi.sh` installiert Samba, legt `scan-inbox` an und kann die Freigabe **PaperMind Scans** automatisch in `/etc/samba/smb.conf` eintragen.

Auf dem iPhone verbindest du dich in der Dateien-App mit:

```text
smb://<PI_IP>/PaperMind Scans
```

Melde dich mit dem Linux-Benutzer des Pi und dem im Setup vergebenen SMB-Passwort an.
