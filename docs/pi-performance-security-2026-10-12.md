# Produktiv-Pi: Performance und Systempakete, 12. Oktober 2026

**Die gemessenen Lesezugriffe laufen stabil; Sicherheitsupdates haben jetzt Vorrang.** Bei höchstens zwei parallelen GETs und vier Anfragen pro Sekunde gab es keine HTTP-Fehler oder Datenbank-Deadlocks. Die Dokumentensuche war mit rund 149 ms Median der langsamste gemessene Zugriff. Die Paketprüfung bestätigt betroffene Versionen von Ghostscript, nginx und Caddys Go-Laufzeit. Diese Prüfung hat keine Systempakete oder Container aktualisiert.

Geprüfter Git-Stand: `acc22ca29a695cdd987624b479d90aa7aed419a3`; aktiver Anwendungs-Snapshot `8a06de418d9b7d94`, Schema `113_drop_note_favorite`. Quellstatus und Container-Identitäten wurden geprüft. Die abschließende Bridge-Statusprüfung bestätigt alle Anwendungsdienste im laufenden beziehungsweise gesunden Zustand. Kein Containerwechsel, keine Migration und kein Pi-Neustart.

## Antwortzeiten auf dem Pi

Die folgende Messreihe lief am 12. Oktober von **12:45:23 bis 12:47:42 MESZ**. Pro Zugriff und Phase: 20 Stichproben nach zwei Aufwärmanfragen. Normal: ein Worker / maximal 2 GETs pro Sekunde; begrenzte Last: zwei Worker / maximal 4 GETs pro Sekunde. Sie umfasst 280 Messanfragen und 28 Aufwärmanfragen. Das Administratorkonto enthält 24 aktive Notizen und 522 aktive Dokumente; eine bestehende Sitzung wurde intern verwendet. Token, Dokument-IDs und Antwortinhalte wurden nicht gespeichert.

| Zugriff | Normal p50 / p95, ms | Begrenzte Last p50 / p95, ms | Übertragene Bytes, Median | Kodierung |
| --- | ---: | ---: | ---: | --- |
| Notizliste, Limit 500 | 31,0 / 45,1 | 30,6 / 44,3 | 5.071 | gzip |
| Dokumentliste, Limit 20 mit Gesamtzahl | 46,7 / 58,6 | 34,3 / 53,5 | 6.274 | gzip |
| Dokumentensuche „Rechnung“, Limit 20 | 148,9 / 163,0 | 148,4 / 157,5 | 8.773 | gzip |
| Notizsuche „Test“, Limit 500 | 56,9 / 76,5 | 45,4 / 52,6 | 4.161 | gzip |
| Import-Inbox, Limit 50 | 39,7 / 47,9 | 39,7 / 51,5 | 283 | identity |
| Vorhandenes Dokument-Thumbnail | 31,4 / 39,0 | 22,8 / 33,8 | 29.261 | identity |
| Erste 64 KiB einer vorhandenen Originaldatei | 31,5 / 37,7 | 23,3 / 36,1 | 65.536 | identity |

Alle Listen-/Bildanfragen lieferten HTTP 200; Datei-Teilabrufe HTTP 206. Die Datei wurde anhand Besitzer, Rolle und Größe gewählt; ihr PDF-Dateityp wurde nicht gesondert validiert. **0 Fehler in beiden Phasen.** Normalphase: 76,54 Sekunden; Lastphase: 38,28 Sekunden. p95 ist aus 20 Werten interpoliert und beschreibt diese kurze Stichprobe, keine garantierte Langzeitgrenze. Die Endpunkte wurden nacheinander gemessen; dies ist ein kontrollierter Vergleich von Lesezugriffen, kein gemischter Dauertest vieler Nutzer.

Eine vorherige Messreihe mit `identity` lieferte für die gleichen drei Listen 17.130, 30.570 beziehungsweise 37.590 Byte: gzip reduziert hier die Übertragung um **70,4 %, 79,5 % beziehungsweise 76,7 %**. Die frühere Notizsuche verwendete einen anderen Suchbegriff ohne Treffer und wird deshalb nicht direkt verglichen. Insgesamt wurden in beiden Messreihen 616 GETs einschließlich Aufwärmanfragen ausgeführt. Die schon aktive Kompression wurde verifiziert; daraus folgt keine neue Vorher-/Nachher-Beschleunigung des Servers.

## Ressourcen und Grenzen der Messung

| Phase | Ressourcen-Stichproben | Host-CPU Mittel / Maximum | Verfügbarer RAM mindestens | Temperatur höchstens | I/O-Wartezeit höchstens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline, etwa 10 Sekunden | 4 | 4,68 % / 10,32 % | 4.947,8 MiB | 54,0 °C | 0 % |
| Normal | 20 | 7,68 % / 16,01 % | 4.863,2 MiB | 53,45 °C | 0,07 % |
| Begrenzte Last | 11 | 11,72 % / 18,92 % | 4.831,2 MiB | 54,55 °C | 0,06 % |

Host-CPU ist über alle Kerne normalisiert; Docker-CPU kann dagegen mehr als 100 % anzeigen. Die Messwerkzeuge und normaler Hintergrundverkehr sind enthalten. Unter dieser begrenzten Last gibt es keinen Hinweis auf CPU-/RAM-Sättigung, thermische Probleme oder erhebliches I/O-Warten. Die globalen DB-Zähler melden in beiden Phasen **0 zusätzliche Deadlocks und 0 zusätzliche Block-Lesezugriffe**. Commit-/Rollback-Zähler enthalten alle Hintergrundzugriffe; Rollbacks beim Schließen lesender Sessions sind kein Nachweis fehlgeschlagener Anfragen.

Gemessen wurde HTTP im Pi-Netz durch Caddy → nginx → Backend, einschließlich Antwortübertragung. **WLAN, externe TLS-Verbindung, Safari-Rendering, Editor, umfangreiche OCR-/KI-Jobs und Langzeitbetrieb sind nicht abgedeckt.** Der Safari-Arbeitsbereich wurde lediglich eingesehen. Eine lange Wartezeit beim lokalen UI-Automationswerkzeug ist kein belastbarer Latenzmesswert der Anwendung. Es gibt keinen Produktionsvergleich mit dem Stand vor den ursprünglichen Optimierungen; die frühere lokale 18-fache Notiz-Verbesserung bleibt ein synthetischer Test.

## Betriebssystem- und Containerpakete

Die feste Inventur vom 12. Oktober, 12:32 MESZ, erfasste **2.658 OS-Paketdatensätze** auf Host und sechs Containern. Binär- und Quellpaketversionen wurden getrennt erhalten, installierte gehaltene Pakete eingeschlossen und Syft-Kataloggrößen gegen die Inventur geprüft. Zusätzlich wurden **145 Go-Komponenten** aus Caddys öffentlicher Build-Metadatenliste erfasst. Der Abgleich lief auf dem Mac ohne Upload der Paketbestände.

Werkzeuge: [Syft v1.54.1](https://github.com/anchore/syft/releases/tag/v1.54.1), [Grype v0.120.1](https://github.com/anchore/grype/releases/tag/v0.120.1), offizielle Release-Archive mit geprüften SHA-256. Grype-Datenbank v6.1.10, erstellt `2026-10-12T06:45:22Z`; gültig und für die Scans ohne automatische Aktualisierung verwendet. Kompakte Ergebnisse, Image-Identitäten und Nachweis-Prüfsummen stehen in [den Messdaten](audits/pi-audit-2026-10-12.json).

| Ziel | Betriebssystem / Laufzeit | OS-Pakete | Scanner-Treffer / verschiedene Advisory-IDs | High/Critical mit veröffentlichtem Fix: Quellpaket-/Advisory-Paare |
| --- | --- | ---: | ---: | ---: |
| Host | Debian 13; Kernel `6.18.33+rpt-rpi-2712`; Docker 29.5.3 | 1.707 | 15.871 / 2.707 | 176 |
| Backend | Debian 13; Python 3.12.15 | 277 | 585 / 292 | 1 |
| Worker | Debian 13; Python 3.12.15 | 343 | 786 / 369 | 1 |
| AI | Debian 13; Python 3.12.15 | 87 | 159 / 67 | 0 |
| Frontend | Alpine 3.21.3; nginx 1.27.5 | 68 | 222 / 169 | 53 |
| DB | Debian 12; PostgreSQL 17.10 | 144 | 559 / 208 | 43 |
| Caddy OS | Alpine 3.23.4 | 32 | 156 / 80 | 48 |

Diese Zählungen sind **Versionsabgleiche, keine Zahl nachgewiesener ausnutzbarer Fehler**. Mehrere Binärpakete desselben Quellpakets erzeugen mehrfach denselben Treffer; Ziele teilen ebenfalls Bibliotheken. Viele Debian-Treffer haben den Herstellerstatus `not-fixed` oder `wont-fix`, einige Alpine-Treffer keinen bekannten Fixstatus. Das bedeutet nicht automatisch „harmlos“ oder „durch ein Upgrade behoben“. Die letzte Spalte dedupliziert je Ziel nach Advisory-ID und Quellpaket. Der große Host-Bestand, insbesondere Kernel-Metadaten, benötigt eine Einzelfallprüfung statt einer pauschalen CVE-Zählung. [Grype erklärt diese Fixzustände](https://oss.anchore.com/docs/guides/vulnerability/filter-results/).

Caddys separate Go-Prüfung ergab **54 Paket-/Advisory-Treffer mit 45 verschiedenen IDs**; 53 Treffer haben einen veröffentlichten Fix. Darunter sind drei Critical-Treffer, von denen zwei dieselbe HTTP/2-Advisory in `stdlib` und `x/net` betreffen. GO-/GHSA-IDs und deren CVE-Aliasse sind keine zusätzliche unabhängige Sicherheitslücke. Es erfolgte keine Analyse tatsächlich aufgerufener Go-Funktionen.

## Priorisierter Patchbedarf

1. **Ghostscript in Backend und Worker:** installiert `10.05.1~dfsg-1+deb13u2`, korrigiert ab `10.05.1~dfsg-1+deb13u3`. Debian bestätigt für **CVE-2026-101258** das Umgehen von `-dSAFER` durch präparierte PostScript-/EPS-Dateien bis zur Befehlsausführung mit den Rechten des Prozesses. Beide Images enthalten Ghostscript für die Dokumentverarbeitung; deshalb ist der Befund für PaperMind relevant. Die konkrete Ausnutzung über einen PaperMind-Upload wurde nicht getestet. [Debian CVE](https://security-tracker.debian.org/tracker/CVE-2026-101258), [DSA-6550-1](https://security-tracker.debian.org/tracker/DSA-6550-1).
2. **Frontend-Image erneuern:** nginx **1.27.5** liegt in veröffentlichten betroffenen Versionsbereichen. Beispielsweise ist der Map-/Regex-Pufferfehler CVE-2026-42533 ab 1.30.4 beziehungsweise 1.31.3 korrigiert. Die Konfiguration enthält eine Regex-Map; das allein beweist keine Ausnutzbarkeit. Weitere Hinweise sind modul-/konfigurationsabhängig. Eine gepflegte aktuelle nginx-Basis wählen und sämtliche nginx-Hinweise gegen deren Konfiguration prüfen. Außerdem ist Alpine-OpenSSL **3.3.3-r0** unter anderem von CVE-2025-15467 betroffen, behoben ab **3.3.6-r0**; spätere Hinweise benötigen neuere Pakete. Diese Lücke betrifft CMS-Verarbeitung, nicht pauschal jede TLS-Verbindung. [nginx-Herstellerhinweise](https://nginx.org/en/security_advisories.html), [Alpine/OpenSSL](https://security.alpinelinux.org/vuln/CVE-2025-15467).
3. **Caddy-Image mit neuer Go-Laufzeit/Modulen ersetzen:** aktive Build-Metadaten: Caddy **2.11.4**, Go **1.26.3**, `golang.org/x/net` **0.55.0**. **GO-2026-6612 / CVE-2026-78663** betrifft HTTP/2-Flusskontrolle und kann Ressourcenverbrauch/DoS verursachen; korrigiert ab Go **1.26.9** und `x/net` **0.60.0**. Da Caddy HTTP/2 bereitstellt, ist dies ein relevanter Prüf- und Patchkandidat; konkrete Funktions-Erreichbarkeit wurde nicht nachgewiesen. Das neue Image muss auch übrige gebündelte Go-Module und Alpine-Pakete abdecken. Die installierten OpenSSL-Bibliotheken beweisen keine Caddy-TLS-Betroffenheit: der Caddy-Build hat `CGO_ENABLED=0`. [Offizieller Go-Hinweis](https://pkg.go.dev/vuln/GO-2026-6612).
4. **DB-Image und Host im Wartungsfenster aktualisieren:** im DB-Image unter anderem OpenSSL `3.0.19-1~deb12u2` und GnuTLS `3.7.9-2+deb12u6`; veröffentlichte Fixstände für einen Teil der Treffer sind `3.0.22-1~deb12u1` beziehungsweise `3.7.9-2+deb12u7`. Auf dem Host unter anderem OpenSSL `3.5.6-1~deb13u2`; veröffentlichter Trixie-Fixstand `3.5.7-1~deb13u3`. PostgreSQL-Hauptversion und pgvector-Kompatibilität beibehalten, vor dem Containerwechsel Sicherung prüfen. Host-Updates dürfen Scanner-/Bridge-Funktion nicht verlieren; ein nötiger Neustart braucht die ausdrückliche Freigabe. Die Verfügbarkeit aller Kandidaten in den konkret eingerichteten APT-/APK-Quellen wurde nicht geprüft. Einige Bookworm-Hinweise bleiben selbst mit dem genannten OpenSSL-Fixstand offen, etwa CVE-2026-84782. [Debian-Herstellerstatus](https://security-tracker.debian.org/tracker/CVE-2026-84782).

Das sind noch ausstehende **Patches**, keine erneut offenen Implementierungsfehler der bereits erledigten 15 Audit-Befunde. Ein Paketupdate entfernt nicht automatisch jeden Scanner-Treffer. Nach dem Patchen die tatsächlich laufenden Images erneut inventarisieren und prüfen; zusätzlich OCR, PDF-Download, Login, Kompression und Gesundheitszustand verifizieren. Die bisherigen festen Rollout-Aktionen sind an den alten Release gebunden und dürfen nicht für beliebige neue Images umfunktioniert werden.

## Abdeckung, Nachweise und nächste Optimierung

Die Inventur erfasst paketverwaltete OS-Komponenten und die genannten öffentlichen Laufzeitversionen; Caddys Go-Modulbestand ist zusätzlich geprüft. npm-/Python-Abhängigkeiten waren Gegenstand des vorherigen Audits und wurden hier nicht erneut vollständig aufgelöst. Raspberry-Pi-Kernel-Backports, Firmware, sonstige manuell installierte Programme, Bibliotheks-Erreichbarkeit und sämtliche nginx-Module sind nicht vollständig geprüft. Die Prüfung enthält keine Exploit-Versuche.

Die freigegebenen Aktionen `performance_audit`, `performance_audit_status`, `security_inventory` sind installiert und auf den geprüften Stand sowie Codeprüfsummen begrenzt. Wiederholtes Starten nach Erfolg liefert den gespeicherten Lauf; ein neues Deployment lässt die Vorprüfung abbrechen. Sicherheitsgrenzen: keine freien Befehle/URLs, keine Weiterleitungen, intern kurzlebiger Token, höchstens 2 MiB Antwort, Prozessalarm nach 180 Sekunden je Phase, Abbruch bei Containeränderungen, API-Fehlern, Backup, Temperatur ab 80 °C oder weniger als 256 MiB verfügbarem RAM. Bridge-/Code-Sicherung und Ergebnisdateien bleiben in festen privaten Verzeichnissen; vollständige lokale Paketberichte liegen außerhalb des Git-Bestands.

**39 Skript-Tests bestanden**, darunter zwölf für Zugriffsbeschränkung, Geheimnisschutz, Grenzen und Inventur sowie vier für Quellpaketversionen, Duplikat-Zählung und Go-Metadaten. Der vollständige Offline-Abgleich prüft die Kataloggröße jedes Zielsystems. App-Quellcode blieb unverändert; Backend-/Frontend-Suites des vorherigen Releases mussten hierfür nicht erneut laufen.

Nach den Sicherheitsupdates ist die **Dokumentensuche** der sinnvollste gezielte Performance-Kandidat: tatsächliche SQL-Pläne und Query-Zeiten für repräsentative Suchbegriffe mit und ohne Treffer messen, anschließend erst einen belegten Engpass ändern. Das vorhandene Ressourcenpolster rechtfertigt derzeit keinen pauschalen Ausbau von Workerzahl oder DB-RAM.
