# PaperMind Scan-Button (Canon LiDE 400)

Scannen per **Hardware-Taste** direkt in PaperMind. Der Scanner hängt per USB am
Pi (Host), nicht im Container. Ein kleiner Poller-Dienst auf dem Host erkennt
Tastendrücke, scannt und legt das fertige PDF in den bestehenden Drop-Ordner
`scan-inbox` – ab da läuft alles **wie bei der SMB-Aktion**:

```
Taste → scanimage (Host) → PDF in scan-inbox/ → Worker erkennt stabile PDF
      → ImportInboxService → Import-Inbox → Badge am "Importieren"-Button
```

Es ist **kein Backend-/Frontend-Code** nötig – der Scanner ist nur ein weiterer
PDF-Produzent für `scan-inbox` (analog zu iOS via SMB, siehe
[`docs/smb-scan-inbox.md`](../../docs/smb-scan-inbox.md)).

**Bedienung** (Flachbett = kein Einzug → ein Tastendruck = eine Seite):

- **button-1-Taste** → Seite scannen und an den laufenden Batch anhängen
- **button-2-Taste** → Batch zu einer mehrseitigen PDF abschließen → Importscreen

Welche der 5 physischen Tasten `button-1` bzw. `button-2` auslöst, ist je nach
Gerät unterschiedlich – einmal ausprobieren (siehe „Tastenzuordnung" unten).

**UI-ausgelöste Scans & Job-Zuordnung.** Wird ein Scan aus dem Importfenster
ausgelöst, reiht das Backend einen Befehl ein; der Worker schreibt ihn als
Datei `.papermind-scan-command-<seq>` nach `scan-inbox`, die der Poller im
selben Loop konsumiert (bitgleich zum Tastendruck). Der Dateiinhalt ist
tab-getrennt: `"<command>\t<job_id>"`. Die Job-ID reicht der Poller per
`PAPERMIND_SCAN_JOB_ID` an `papermind-scan.sh` weiter, das sie als
`__pmjob-<uuid>` in den PDF-Dateinamen einbettet. Der Worker löst den Marker
wieder heraus (bereinigt den Anzeigenamen) und ordnet den Hardwarelauf so
**exakt** dem auslösenden Backend-Job zu. Das Altformat ohne Tab (nur das
Kommando) bleibt unterstützt – dann ohne Job-Zuordnung.

> Nach Änderungen an `papermind-scan.sh`/`papermind-scan-watch.sh` den
> Host-Dienst neu starten: `sudo systemctl restart papermind-scan-watch`.

## Warum ein eigener Poller statt scanbd?

Bei der LiDE 400 läuft der Scanner über das **`pixma`**-SANE-Backend. Der
naheliegende `scanbd` ("scanner button daemon") erwies sich hier als dreifach
fragil: verrauschte Buttonwerte (unzuverlässiges Triggern), ein Geräte-Konflikt
(scanbd hält das Gerät offen, das Action-Script will gleichzeitig scannen) und
eine DBus-Policy-Hürde. Der hier verwendete Poller umgeht all das: **ein**
Prozess liest die Tasten über `scanimage -A` und scannt anschließend selbst –
sequenziell, also nie ein Konflikt ums Gerät.

> Pfade unten gehen von `/home/jan/papermind` aus. Bei abweichender Position alle
> Pfade (Scripte, `.service`) entsprechend anpassen.

---

## 1. Pakete installieren (auf dem Pi)

```bash
sudo apt update
sudo apt install -y sane-utils img2pdf
# img2pdf erzeugt verlustfreie PDFs. Alternativ tut es ImageMagick ("convert").
# scanbd wird NICHT benötigt.
```

## 2. Scanner erkennen

```bash
scanimage -L
# Erwartet:  device `pixma:04A91912_50F25C' is a CANON CanoScan LiDE 400 ...
```

Wird der Scanker nicht (oder nur als `escl:`/`airscan:`) gefunden, siehe
Abschnitt **ipp-usb** unten.

## 3. ipp-usb deaktivieren (wichtig!)

Der Dienst `ipp-usb` belegt das USB-Gerät exklusiv für eSCL/IPP-over-USB und
blockiert damit den `pixma`-Direktzugriff (Symptom: `ScannerCarriageLockError`
oder `Error during device I/O`). Da die LiDE 400 ein reiner Scanner ist, kann er
gefahrlos maskiert werden:

```bash
sudo systemctl mask --now ipp-usb
# danach USB-Kabel kurz ab- und wieder anstecken
scanimage -L   # sollte jetzt nur noch pixma:... zeigen
```

Falls `scanbd` installiert ist, ebenfalls abschalten (sonst belegt es das Gerät):

```bash
sudo systemctl disable --now scanbd 2>/dev/null || sudo systemctl mask scanbd
```

## 4. Scripte ausrollen

Per git (oder `scp`) den Ordner `deploy/scan-button/` auf den Pi bringen, dann:

```bash
chmod +x /home/jan/papermind/deploy/scan-button/papermind-scan.sh
chmod +x /home/jan/papermind/deploy/scan-button/papermind-scan-watch.sh
```

Kurzer Funktionstest ohne Tasten (legt eine 1-seitige PDF in der Inbox ab):

```bash
/home/jan/papermind/deploy/scan-button/papermind-scan.sh page
/home/jan/papermind/deploy/scan-button/papermind-scan.sh finish
```
→ In PaperMind sollte die Badge am **Importieren**-Button erscheinen.

## 5. Poller-Dienst installieren

```bash
sudo cp /home/jan/papermind/deploy/scan-button/papermind-scan-watch.service \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now papermind-scan-watch.service
systemctl status papermind-scan-watch.service --no-pager   # active (running)?
```

## 6. Tastenzuordnung ermitteln

Tasten drücken und im Log mitlesen, welche `button-1` (page) bzw. `button-2`
(finish) auslöst:

```bash
journalctl -t papermind-scan-watch -t papermind-scan -f
```

Drück die 5 Tasten durch; merk dir die zwei, die `Seite scannen` bzw.
`Batch abschließen` auslösen. (Die übrigen lösen denselben Sensor aus oder nichts.)

## Alltag

1. Seite auflegen → **button-1-Taste** → Seite landet im Batch.
2. Nächste Seite → **button-1** → usw.
3. Am Ende **button-2-Taste** → alle Seiten werden zu **einer** PDF und
   erscheinen als ein Eintrag im Importscreen (ggf. App kurz neu laden).

## (Optional) Live-Modus: jede Seite sofort senden

Standardmäßig sammelt **button-1** Seiten lokal und erst **button-2**
schickt sie als fertige PDF ab. Alternativ kann pro Scanner in den
**Scanner-Einstellungen** der App ("Seiten sofort senden") ein Live-Modus
aktiviert werden: jede mit **button-1** gescannte Seite wird sofort als
eigene 1-Seiten-PDF nach `scan-inbox/` gelegt. Bei offenem Importfenster
erscheinen die Seiten dort nacheinander als ein wachsendes Dokument -
**button-2** wird in diesem Modus nicht mehr benötigt.

Die Einstellung wird vom Worker alle paar Sekunden in
`scan-inbox/.papermind-scanner-config` gespiegelt; dieses Script liest nur
diese Datei (kein Netzwerkzugriff, kein zusätzliches Setup auf dem Pi nötig).

## Scanvorgang im Importfenster sichtbar machen

Während `scanimage` läuft, schreibt dieses Script in
`scan-inbox/.papermind-scanner-status` (umgekehrte Richtung zur
`.papermind-scanner-config`-Datei oben: Host → App, nicht von Hand anfassen).
Der Worker liest diese Datei alle paar Sekunden und spiegelt sie in die
Datenbank; das Importfenster zeigt daraufhin eine pulsierende
"Scanne…"-Platzhalterkarte, solange ein Scan läuft. Kein zusätzliches Setup
nötig - die Datei wird automatisch verwaltet (auch bei einem
`scanimage`-Fehler, z. B. USB-Disconnect, wird der Status garantiert wieder
zurückgesetzt).

## (Optional) Idle-Sicherheitsnetz

Schließt einen vergessenen Batch nach `IDLE_SECONDS` (Default 180) Ruhe
automatisch ab:

```bash
sudo cp /home/jan/papermind/deploy/scan-button/papermind-scan-idle.service \
        /etc/systemd/system/
sudo cp /home/jan/papermind/deploy/scan-button/papermind-scan-idle.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now papermind-scan-idle.timer
```

---

## Konfiguration (Environment)

Für den Poller-Dienst in `papermind-scan-watch.service`, für Scan-Parameter ggf.
in `papermind-scan.sh` (oder als `Environment=` in der `.service`):

| Variable          | Default                         | Bedeutung                                    |
| ----------------- | ------------------------------- | -------------------------------------------- |
| `SCAN_DEVICE`     | *(auto: erster pixma-Scanner)*  | SANE-Device aus `scanimage -L`               |
| `ACTIVE_POLL_INTERVAL` | `0.7`                      | Tasten-Abfrage-Intervall kurz nach einer Aktion (schnell) |
| `IDLE_POLL_INTERVAL`   | `3`                        | Tasten-Abfrage-Intervall in Ruhe (Normalfall, schont USB) |
| `ACTIVE_WINDOW_SECONDS`| `10`                       | Wie lange nach einer Taste das schnelle Intervall gilt |
| `SCAN_INBOX_DIR`  | *(aus Repo-Pfad abgeleitet)*    | Drop-Ordner (= Host-Mount von `/scan-inbox`) |
| `SCAN_RESOLUTION` | `300`                           | DPI                                          |
| `SCAN_MODE`       | `Color`                         | `Color` \| `Gray` \| `Lineart`               |
| `IDLE_SECONDS`    | `180`                           | Ruhezeit für `finalize-idle`                 |

`scan-inbox`-Stabilitätsfenster (`IMPORT_INBOX_FILE_STABLE_SECONDS`, Default 3s)
und der Mount stehen in `docker-compose.yml` / `.env`.

## Fehlersuche

| Symptom | Ursache / Lösung |
| --- | --- |
| `scanimage -L` zeigt nur `escl:`/`airscan:` | `ipp-usb` maskieren (Schritt 3), USB neu stecken |
| `ScannerCarriageLockError` / `Error during device I/O` | meist `ipp-usb` aktiv; sonst Transportverriegelung am Gerät / USB-Strom |
| Taste tut nichts | `journalctl -t papermind-scan-watch -f`; richtige Taste? Dienst `active`? |
| `device busy` im Scan | Läuft noch `scanbd`/`ipp-usb`? Beide abschalten (Schritt 3) |
| Scan bricht ~60% ab, `usb ... disconnect` | USB-Strom: Pi-5-Netzteil (5V/5A) oder aktiver USB-Hub |
| PDF erscheint nicht in der App | App neu laden; Worker-Log: `import inbox drop processed`; PDF in `scan-inbox/.papermind-processed/`? |
| Worker-Log: `exceeds maximum allowed size`, PDF landet in `scan-inbox/.papermind-failed/` | `UPLOAD_MAX_BYTES` zu niedrig für mehrseitige Color-Scans (~15 MB/Seite bei 300dpi). In `.env.prod` erhöhen (Default jetzt 100 MB) und `backend`+`worker` neu starten. |

## Dateien

| Datei | Zweck |
| --- | --- |
| [`papermind-scan-watch.sh`](./papermind-scan-watch.sh) | Poller: liest Tasten, ruft `page`/`finish` |
| [`papermind-scan-watch.service`](./papermind-scan-watch.service) | systemd-Dienst für den Poller |
| [`papermind-scan.sh`](./papermind-scan.sh) | scannt (`page`), baut PDF (`finish`), Idle-Abschluss |
| [`papermind-scan-idle.service`](./papermind-scan-idle.service) / [`.timer`](./papermind-scan-idle.timer) | optionales Idle-Sicherheitsnetz |

## Verwandt

- Drop-Ordner-Pipeline & SMB: [`docs/smb-scan-inbox.md`](../../docs/smb-scan-inbox.md)
- Host-Helfer-Muster (gleiche Idee, unprivilegierter Container):
  [`deploy/host-control/`](../host-control/)
