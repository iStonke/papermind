# Feste Performance- und Paketprüfung: freigegeben

**Abgeschlossen:** Die beiden Messreihen, Paketinventur und der lokale Schwachstellenabgleich stehen im [Ergebnisbericht](pi-performance-security-2026-10-12.md). Die folgenden Punkte dokumentieren die freigegebene Methode.

Der Nutzer hat Performance-Messungen bei normaler Nutzung und begrenzter Last sowie anschließend den Sicherheitsabgleich der Betriebssystem- und Containerpakete beauftragt. Der zuletzt geprüfte Produktivstand ist `acc22ca`; alle Dienste sind gesund. Vor dem tatsächlichen Lauf prüft der feste Runner Revision, Quellstatus, Codeprüfsummen und Containerzustand erneut.

## Performance

- Zehn Sekunden Ressourcen-Baseline; anschließend je 20 Stichproben und zwei Aufwärmanfragen für Notizliste, Dokumentliste, beide Suchlisten und Import-Inbox. Wenn passende bereits vorhandene Dateien im Administratorkonto vorhanden sind, werden Thumbnail und die ersten 64 KiB eines PDF ebenfalls gemessen.
- Normal: ein Worker, maximal zwei Anfragen pro Sekunde. Begrenzte Last: zwei Worker, maximal vier Anfragen pro Sekunde. Pro Phase gelten zusätzlich eine harte Prozesslaufzeit von 180 Sekunden und ein Antwortlimit von 2 MiB. Keine Benutzerparameter oder frei wählbaren URLs.
- HTTP-GETs durch Caddy, nginx und Backend innerhalb des Pi-Netzes. Keine Umstellung von Containern, Datenbank oder Anwendung. Vorhandene Auth-Sitzung wird intern gelesen und ein kurzlebiger Testtoken erzeugt; Token, Dokument-IDs und Antwortinhalte werden nicht ausgegeben oder gespeichert. Weiterleitungen und Umgebungs-Proxys sind deaktiviert.
- p50/p95/Maximalzeit, HTTP-Status/Fehler, Antwortgrößen, CPU, RAM, I/O-Wartezeit und Temperatur. DB-Zähler werden nur gelesen; ihre globalen Differenzen enthalten auch Hintergrundverkehr.
- Abbruch bei laufendem Backup, unbekanntem Quellstand, veränderten Containern, API-Fehlern, Temperatur ab 80 °C oder weniger als 256 MiB verfügbarem RAM.
- Die Messung umfasst keine WLAN-/TLS-Strecke und kein Browserrendering. Der reale Safari-Arbeitsbereich ist angemeldet; der offene Notizinhalt wird nicht bearbeitet. Ein Browserprofil erfordert gesondert geeignete Messmöglichkeiten.

## Sicherheitsabgleich

Eine feste Inventur liest Paketnamen, binäre und Quellpaketversionen, Architektur und Betriebssystemkennung von Host und den sechs laufenden Containern. Sie liest zusätzlich die öffentlichen Laufzeitversionen von Python, nginx, PostgreSQL, Caddy und Docker. Keine Schlüssel, Passwörter, Dokumente oder Umgebungswerte werden ausgegeben.

Die Bestände werden auf dem Mac mit offiziell heruntergeladenen, SHA-256-geprüften Syft-/Grype-Binaries und einer lokal aktualisierten Schwachstellendatenbank abgeglichen. Paketbestände werden nicht an einen externen Prüfdienst übertragen. Abdeckung und Grenzen, insbesondere Raspberry-Pi-Kernel und nicht paketverwaltete Binärkomponenten, müssen im Ergebnis ausdrücklich ausgewiesen werden. Diese Prüfung installiert keine Updates auf dem Pi.

## Zugriff

Der Nutzer hat die Erweiterung um die festen Bridge-Aktionen `performance_audit`, `performance_audit_status` und `security_inventory` sowie deren Ausführung ausdrücklich freigegeben. `AGENTS.md` und `CLAUDE.md` dokumentieren die begrenzte zusätzliche Zugriffsliste. Umsetzung: `scripts/pi_audit.py`, `scripts/pi_performance_probe.py`, `scripts/install_pi_audit_bridge.py`; zwölf Verhaltenstests in `scripts/tests/test_pi_audit.py` bestehen.
