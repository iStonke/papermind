# PaperMind Scan-Button (Canon LiDE 400)

Scannen per **Hardware-Taste** direkt in PaperMind. Der Scanner hängt per USB am
Pi (Host), nicht im Container. Beim Tastendruck scannt der Host und legt das
fertige PDF in den bestehenden Drop-Ordner `scan-inbox` – ab da läuft alles
**genau wie bei der SMB-Aktion**:

```
Taste -> scanimage (Host) -> PDF in scan-inbox/ -> Worker erkennt stabile PDF
      -> ImportInboxService -> Import-Inbox -> Badge am "Importieren"-Button
```

Es ist **kein Backend-/Frontend-Code** nötig – der Scanner ist nur ein weiterer
PDF-Produzent für `scan-inbox` (analog zu iOS via SMB, siehe
[`docs/smb-scan-inbox.md`](../../docs/smb-scan-inbox.md)).

Flachbett = kein Einzug → **ein Tastendruck = eine Seite**. Mehrseitige
Dokumente werden als *Batch* gesammelt und mit einer zweiten Taste (oder per
Idle-Timeout) zu einer PDF abgeschlossen.

> Pfade unten gehen von `/home/pi/papermind` aus. Bei abweichender Repo-Position
> alle Pfade (Script, `.conf`, `.service`) entsprechend anpassen.

---

## 1. Pakete installieren (auf dem Pi)

```bash
sudo apt update
sudo apt install -y sane-utils scanbd img2pdf
# img2pdf erzeugt verlustfreie PDFs. Alternativ tut es ImageMagick ("convert").
```

## 2. Scanner erkennen

```bash
scanimage -L
# Erwartet etwa:  device `genesys:libusb:001:004' is a Canon LiDE 400 flatbed scanner
```

- Wird **nichts** gefunden: SANE/genesys-Version prüfen (`scanimage --version`,
  die LiDE 400 braucht sane-backends ≥ 1.0.28). USB-Kabel direkt am Pi, nicht
  über Hub ohne eigene Versorgung.
- Den Device-String (z. B. `genesys:libusb:001:004`) brauchst du **nicht**
  zwingend – ohne `SCAN_DEVICE` nimmt das Script den Default-Scanner. Bei mehr
  als einem Scanner `SCAN_DEVICE` setzen (Service-Datei / Env).

Ein Testscan (legt direkt eine 1-seitige PDF in der Inbox ab):

```bash
SCAN_INBOX_DIR=/home/pi/papermind/scan-inbox \
  /home/pi/papermind/deploy/scan-button/papermind-scan.sh page
SCAN_INBOX_DIR=/home/pi/papermind/scan-inbox \
  /home/pi/papermind/deploy/scan-button/papermind-scan.sh finish
```
Danach sollte in PaperMind die Badge am **Importieren**-Button erscheinen.

## 3. Tastennamen ermitteln

```bash
sudo systemctl stop scanbd 2>/dev/null || true
scanbd -f -d7      # Tasten am Scanner drücken, ausgegebene Sensor-Namen ablesen
                   # (Strg+C zum Beenden)
```

Bei der LiDE 400 heißen die 5 Tasten meist: `scan`, `file`, `email`, `copy`,
`extra` (die **PDF-Taste** ist `file`). Passt das nicht, die `filter`-Regex in
[`scanbd-papermind.conf`](./scanbd-papermind.conf) anpassen.

## 4. scanbd verdrahten

Script ausführbar machen und Aktionen in scanbd einbinden:

```bash
chmod +x /home/pi/papermind/deploy/scan-button/papermind-scan.sh

# Variante A – per include in /etc/scanbd/scanbd.conf (am Dateiende einfügen):
#   include("/home/pi/papermind/deploy/scan-button/scanbd-papermind.conf")
# Variante B – Inhalt der .conf direkt in den passenden device-Block kopieren.
```

In `/etc/scanbd/scanbd.conf` außerdem sicherstellen, dass scanbd als ein
Benutzer läuft, der den Scanner **und** den Drop-Ordner nutzen darf
(üblich: `user = saned`, `group = scanner`).

Ordnerrechte setzen, damit dieser Benutzer in `scan-inbox` schreiben darf und
der Container (root) die PDFs lesen kann:

```bash
sudo chgrp -R scanner /home/pi/papermind/scan-inbox
sudo chmod -R g+rws   /home/pi/papermind/scan-inbox   # setgid: neue Dateien erben Gruppe
sudo usermod -aG scanner saned                        # falls nötig
```

scanbd (neu)starten:

```bash
sudo systemctl enable --now scanbd
sudo systemctl restart scanbd
journalctl -u scanbd -f      # Tastendrücke mitlesen
```

## 5. Mehrseitig scannen (Alltag)

1. Seite auflegen → **Scan-Taste** drücken → Seite landet im Batch.
2. Nächste Seite auflegen → **Scan-Taste** → usw.
3. Am Ende **PDF/file-Taste** drücken → alle Seiten werden zu **einer** PDF
   zusammengefasst und erscheinen als ein Eintrag im Importscreen.

## 6. (Optional) Idle-Sicherheitsnetz

Falls die Abschluss-Taste mal vergessen wird, schließt ein Timer einen Batch
automatisch ab, sobald er `IDLE_SECONDS` (Default 180s) ruht:

```bash
sudo cp /home/pi/papermind/deploy/scan-button/papermind-scan-idle.service \
        /etc/systemd/system/
sudo cp /home/pi/papermind/deploy/scan-button/papermind-scan-idle.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now papermind-scan-idle.timer
```

---

## Konfiguration (Environment)

| Variable          | Default                            | Bedeutung                                   |
| ----------------- | ---------------------------------- | ------------------------------------------- |
| `SCAN_INBOX_DIR`  | `/home/pi/papermind/scan-inbox`    | Drop-Ordner (= Host-Mount von `/scan-inbox`)|
| `SCAN_DEVICE`     | *(leer = Default-Scanner)*         | SANE-Device aus `scanimage -L`              |
| `SCAN_RESOLUTION` | `300`                              | DPI                                         |
| `SCAN_MODE`       | `Color`                            | `Color` \| `Gray` \| `Lineart`              |
| `IDLE_SECONDS`    | `180`                              | Ruhezeit für `finalize-idle`                |

`scan-inbox`-Stabilitätsfenster (`IMPORT_INBOX_FILE_STABLE_SECONDS`, Default 3s)
und der Mount stehen in `docker-compose.yml` / `.env`.

## Fehlersuche

| Symptom | Ursache / Lösung |
| --- | --- |
| `scanimage -L` findet nichts | USB direkt am Pi; sane-backends-Version; `lsusb` zeigt Canon? |
| Taste tut nichts | `journalctl -u scanbd -f`; `filter`-Regex vs. echte Tastennamen (Schritt 3) |
| `scanimage: Device busy` | scanbd hält das Device – Script läuft serialisiert; nicht parallel `scanimage` aufrufen |
| PDF erscheint nicht in der App | Datei wirklich als `*.pdf` (nicht Dot-Datei) in `scan-inbox`? Worker-Logs: `import inbox drop processed` |
| PDF da, aber falscher Besitzer | Schritt 4 Ordnerrechte (`scanner`-Gruppe, setgid) |
| Container kann PDF nicht lesen | Gruppen-/Leserechte auf `scan-inbox` prüfen |

## Verwandt

- Drop-Ordner-Pipeline & SMB: [`docs/smb-scan-inbox.md`](../../docs/smb-scan-inbox.md)
- Host-Helfer-Muster (gleiche Idee, unprivilegierter Container):
  [`deploy/host-control/`](../host-control/)
