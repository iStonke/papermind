# Sicherheitsrelease vom 12. Oktober 2026

## Stand

Der Nutzer hat die Umsetzung der priorisierten Updates, den kontrollierten Pi-Rollout, die gezielte Suchoptimierung sowie die anschließende Bereinigung und den Betrieb ohne Root beauftragt. **Der Anwendungsrelease `01d1c53` und die 103 ausgewählten Host-Sicherheitsupdates sind auf dem Pi installiert und erfolgreich live geprüft.** Die erneute Performance-Messung ist erfolgreich. SSH und D-Bus verwenden noch alte Bibliotheken im Speicher; deren Aktivierung durch einen kontrollierten Pi-Neustart benötigt noch die ausdrückliche Freigabe.

## Geprüfte Änderung

- Backend/Worker: gepinnte Python-3.12.15-/Debian-13-Basis, aktuelle Systempakete und Ghostscript mindestens `10.05.1~dfsg-1+deb13u3`. Der Build verweigert einen älteren Ghostscript-Stand.
- Frontend: nginx `1.30.5` mit aktualisierten Alpine-Paketen; Build mit Node 24. Die kopierten Assets übernehmen keine Root-Eigentümer. nginx schreibt PID und temporäre Dateien nach `/tmp`.
- Caddy: `2.11.7`, aus Standardmodulen mit Go `1.27.2` gebaut. Go-Modulversionen und Prüfsummen sind festgehalten; Netzwerk-/Crypto-/gRPC-/Telemetry-Module erfüllen die überprüften Fixstände. Buildparallelität ist auf zwei begrenzt. Offizielle Basisimages sind per Multiarch-Digest gepinnt.
- DB: PostgreSQL `17.11`, pgvector-Basis `0.8.7`, weiterhin Debian 12 und PostgreSQL-Hauptversion 17. SQL-Erweiterungen werden nicht automatisch aktualisiert. Der Runner prüft Erweiterungen, logische Plugins, Kollationsstand und den Vektoroperator vor/nach dem Wechsel. [PostgreSQL nennt die Voraussetzungen des Minor-Updates](https://www.postgresql.org/docs/17/release-17-11.html).
- Alle Produktionsdienste laufen mit UID 1000 beziehungsweise PostgreSQL mit UID 999, ohne effektive Linux-Capabilities und mit `no-new-privileges`. UID 1000 entspricht den vorhandenen privaten Schlüssel-, Scanner- und Steuerungs-Mounts. Benötigte Volume-Eigentümer werden erst nach Sicherung und Schreibsperre migriert; bisherige UID/GID/Modi werden privat für den Rückfall gesichert. Die TLS-CA-Prüfsumme muss erhalten bleiben.
- Docker-Kontexte schließen `.env`-Dateien, Laufzeitdaten, Git-Verzeichnisse und Schlüsseldateien aus.

Der lokale Offline-Abgleich der sechs neuen Images und ihrer Go-Metadaten findet **keine High-/Critical-Treffer mit veröffentlichtem Fix**. Ungefixte/Hersteller-ignorierte Debian-Treffer sowie wenige Alpine-Hinweise bleiben bestehen. Ein Modulhinweis ohne bekannten Fix betrifft [GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932), das ungewartete `x/crypto/openpgp`. Die zusätzliche Binär-/Symbolprüfung mit **govulncheck v1.9.0** findet keine betroffenen Symbole oder importierten Pakete, nur diesen Modulhinweis. Go-Laufzeit und sämtliche aufgezeichneten Modulversionen der geprüften lokalen Binärdatei stimmen exakt mit dem Pi-Kandidaten überein. Diese [Symbolprüfung hat Grenzen](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck); sie ist kein allgemeiner Nachweis fehlender Ausnutzbarkeit. Es wird kein vollständig schwachstellenfreies System behauptet. Die tatsächlich auf dem Pi gebauten Kandidaten stimmen in allen sechs OS-Paketbeständen und den Go-Metadaten exakt mit den freigegebenen Versionen überein. Auch deren separater Offline-Abgleich findet keine High-/Critical-Treffer mit veröffentlichtem Fix.

## Suchoptimierung

Die feste lesende Produktionsmessung bestätigt den Engpass: für „Rechnung“ insgesamt 147,8 ms Servicezeit, Hauptabfrage 108,6 ms; Auswahl/Sortierung etwa 7,3 ms. Für „Test“ waren es 210,7 ms Servicezeit und 157,4 ms Hauptabfrage. Die Treffertexte (`ts_headline`) beanspruchen den größten Teil. Der Suchbegriff ohne Treffer benötigte 17,0 ms. Pläne enthalten nur Knotentypen, öffentliche Schema-/Indexnamen und Zahlen; keine Dokumenttexte oder IDs.

Der neue Cache speichert ausschließlich kurze Treffertexte für bereits mit Owner-Scope/RLS gelesene Resultatzeilen. Schlüssel: Besitzer, Dokument, Änderungszeit, Suchbegriff und Sprach-/Headline-Konfiguration. Änderungszeiten werden von der bestehenden DB-Triggerfunktion gesetzt. Höchstens 512 Einträge, 120 Sekunden TTL, maximal 8 KiB je gecachtem Text. Große Texte bleiben ungecacht. Ranking, Sortierung, Filter und Gesamtzahl bleiben DB-Abfragen. Tests bestätigen identische wiederholte Treffer, sofortige Invalidierung nach gespeicherter Textänderung und fehlenden Zugriff eines anderen Kontos. Die neue Pi-HTTP-Messreihe bestätigt den Effekt für wiederholte Suchen; kalte Suchen benötigen weiterhin die Treffertext-Erzeugung.

## Alte PDF-Versionen

Der Worker prüft stündlich bekannte generierte Versionsnamen in kanonischen Dokumentverzeichnissen. Er entfernt höchstens 100 mindestens 14 Tage alte, vollständig unreferenzierte PDF-/Thumbnail-Dateien. Aktuelle `DocumentFile`- und `storage_key`-Referenzen werden erhalten, auch aus anderen Dokumenten und dem Papierkorb. Aktive Jobs, gesperrte Dokumente, Symlinks, unbekannte Dateinamen und frische Dateien werden ausgelassen. Schreib-/Wartungssperren sowie Dokument-Row-Locks sichern Publikation und Backup ab. Der Lauf hat zusätzlich ein Zeit-/Inspektionsbudget. Die Bereinigung löscht keine sichtbaren Dokumente.

## Validierung vor dem Pi-Staging

- **631 Backend-Tests und 32 zusätzliche Subtests** bestanden, auch gegen das neue PostgreSQL-17.11-Image mit UID 999 und ohne Capabilities; alle Migrationen bis 113. Keine übersprungenen Tests. Sechs bestehende Bibliotheks-/Test-Warnungen.
- **692 Frontend-Tests** mit Node 24, Produktionsbuild und Größenbudgets bestanden; `npm audit` ohne bekannte Schwachstellen.
- **57 Skript-Tests** vor Staging bestanden. Die abschließende Erweiterung umfasst **62 bestandene Skript-Tests**, einschließlich fehlgeschlagener Host-Sicherung und der vorbereiteten Neustart-Sperren.
- Rootloses Backend und Worker: synthetisches großes PDF, Thumbnail, native OCR, durchsuchbares OCRmyPDF und Piper erfolgreich. Rootloser nginx: Gesundheit und HTTP 401 für anonymen API-Zugriff. Vollständiger rootloser TLS-Proxy Caddy → nginx → Backend: HTTP 200.
- Bestehende produktive Container wurden während der lokalen Prüfung nicht gewechselt. Frühere Diagnose-/Rollout-Aktionen behalten ihre ursprünglichen Bindungen.

## Kontrollierter Wechsel

Die neue feste Bridge bereitet ausschließlich diesen Release vor. Sie prüft `acc22ca`, saubere Quellen und gesunde Container, baut die Kandidaten separat und ermöglicht deren Paketabgleich. Der eigentliche Wechsel benötigt einen erfolgreichen frischen verschlüsselten NAS-Backup-Lauf und die Prüfung sämtlicher Artefakt-Hashes und Manifest-HMAC. Danach folgen Schreibsperre, Stoppen der App-Dienste, gesicherter Eigentümerwechsel, fester Git-Fast-Forward und Containerwechsel. Bei Fehlern werden die ursprünglichen Images, Eigentümer und Git-Revision wiederhergestellt. Keine frei wählbaren Refs, Hosts, Images, Shelltexte oder echten `.env`-Änderungen; kein Pi-Neustart.

Nach dem Wechsel werden UID/Capabilities, RLS, native PDF/OCR/Piper-Funktionen, Paketbestände, bestehende TLS-CA und begrenzte HTTP-Last erneut geprüft. Anschließend folgen die festen Host-Sicherheitsupdates und eine Scanner-/Dienstprüfung. Die Live-Prüfung bestätigt alle sechs gesunden Dienste, die vorgesehenen UIDs und null effektive Capabilities. Schema 113, Owner-Scope/RLS, synthetisches PDF, Thumbnail, native OCR, durchsuchbares PDF und Piper (26.184 Audioframes) bestehen. HTTPS prüft den Hostnamen `papermind` gegen die bestehende CA; HTML/JavaScript werden erfolgreich geliefert, JavaScript mit gzip (48.621 Transferbytes). Anonyme Notizabrufe erhalten sowohl direkt als auch durch den HTTPS-Proxy HTTP 401. Die geprüfte verschlüsselte NAS-Sicherung umfasst 1.224.151.840 Byte. Die bestehenden TLS-CA und SQL-Erweiterungen bleiben erhalten. Die laufenden OS-/Go-Bestände stimmen exakt mit den freigegebenen Versionen überein; auch die 50/41/24 Python-Paketversionen in Backend/Worker/AI entsprechen den separat geprüften lokalen Images.

## Host-Sicherheitsupdates

Der Nutzer hat [den Root-Helfer und die sudoers-Datei](host-security-setup-2026-10-12.md) im Pi-Terminal installiert. Eigentümer, Modi, Helfer-SHA-256 und sudoers-Syntax sind geprüft. Der Helfer akzeptiert ausschließlich fünf feste Aktionen und erzeugt seinen versionsgebundenen APT-Plan selbst aus den 103 ausgewählten Sicherheitspaketen. Root-eigene Dateien, eine minimale Umgebung, SHA-256 in sudoers, Abbruch bei neuen/entfernten Paketen und ausgeschlossenen Systemübergängen begrenzen den Zugriff. Kein Passwort wird an die Bridge übertragen.

Die 103 geprüften Versionsübergänge wurden nach erneut unverändertem Paketplan und **zusätzlicher verifizierter verschlüsselter NAS-Sicherung mit 1.224.154.064 Byte** installiert. Keine Pakete wurden hinzugefügt oder entfernt; Kernel, Docker, systemd und OpenSSH-Paketversionen wurden nicht umgestellt. Der Host enthält weiterhin 1.707 Pakete; der laufende Kernel bleibt `6.18.33+rpt-rpi-2712`. Beispiele sind OpenSSL `3.5.7`, Ghostscript `10.05.1~dfsg-1+deb13u3`, aktualisierte Python-3.13-/Expat-/GLib-/Samba-/curl-Pakete. Alle 103 installierten Versionen entsprechen dem freigegebenen Plan.

Der erneute Offline-Abgleich des tatsächlichen Host-Bestands findet **null High-/Critical-Treffer mit veröffentlichtem Fix**; vorher waren es 176 Quellpaket-/Advisory-Paare beziehungsweise 409 Pakettreffer. 127 Treffer mit Fix bei niedrigerem oder unbekanntem Schweregrad (43 Medium, 3 Low, 15 Negligible, 66 Unknown) sowie `not-fixed`-/`wont-fix`-Hinweise bleiben erfasst. Das sind Versionsabgleiche, keine nachgewiesenen Exploits. Alle sechs laufenden App-Images und Go-Metadaten bleiben unverändert und haben ebenfalls null High-/Critical-Treffer mit veröffentlichtem Fix.

Die Live-Funktionsprüfung nach APT besteht erneut: sechs gesunde/laufende Dienste, vorgesehene UIDs, keine effektiven Capabilities, anonymer Notizabruf HTTP 401, synthetisches PDF, native OCR, Piper (26.624 Frames), HTTPS gegen die bestehende CA sowie gzip. Scanner-Poller aktiv, Canon erkannt, USB aktiv.

**Noch offen: Aktivierung geladener Host-Bibliotheken.** Die feste reine Metadatenprüfung findet bei `ssh.service` noch eine gelöschte alte `libcrypto.so.3`, bei `dbus.service` eine alte `libexpat.so.1` in den Prozess-Mappings. Das Fehlen von `/var/run/reboot-required` genügt daher hier nicht als Nachweis abgeschlossener Aktivierung. UDisks, Samba und Winbind wurden von den Paketskripten bereits neu gestartet. Der vorbereitete einmalige Neustart verwendet die bestehende feste Host-Steuerung, benötigt gesunde unveränderte Quellen/Dienste, eine verifizierte höchstens 24 Stunden alte Sicherung, Schema 113 und keine aktiven/queued Jobs, Backups, Wartung oder vorgemerkten Power-Aktionen. Eine Schreibsperre verhindert neue Änderungen vor dem Neustart. Die Neustart-Aktion ist bis zur ausdrücklichen Freigabe nicht in der Bridge registriert.

## Produktionsmessung nach dem Wechsel

Messung: `2026-10-12T14:54:03.097671+00:00` bis `2026-10-12T14:56:22.426543+00:00`, dieselben sieben GET-Fälle, zwei Aufwärmanfragen und 20 Stichproben je Route/Phase. Die Dokumentzahl bleibt 522; aktive Notizen ändern sich von 24 auf 23. Der Vergleich anderer Routen ist deshalb eine kurze Betriebsstichprobe, kein vollständig identischer Datenbestand. Keine HTTP-Fehler in 280 Messanfragen plus 28 Aufwärmanfragen.

| Zugriff | Normal p50 / p95, ms | Begrenzte Last p50 / p95, ms |
| --- | ---: | ---: |
| Notizliste | 37.3 / 44.3 | 39.0 / 46.3 |
| Dokumentliste | 34.3 / 55.1 | 35.1 / 53.3 |
| Dokumentensuche „Rechnung“ | 47.2 / 66.2 | 65.9 / 72.3 |
| Notizsuche „Test“ | 46.4 / 65.7 | 45.9 / 53.6 |
| Import-Inbox | 28.0 / 42.7 | 28.5 / 44.3 |
| Thumbnail | 24.9 / 33.8 | 23.2 / 36.3 |
| Erste 64 KiB der Originaldatei | 23.3 / 56.3 | 33.4 / 38.6 |

Die wiederholte Suche sinkt im Normalbetrieb von **148,9 auf 47,2 ms** (68,3 %; Faktor 3,15), unter begrenzter Last von **148,4 auf 65,9 ms** (55,6 %; Faktor 2,25). Die erste kalte Aufwärmanfrage benötigt **167,3 ms**, danach 48,9 ms. Der Cache verbessert wiederholte Anfragen innerhalb der 120-Sekunden-TTL; er macht keine pauschale Beschleunigungszusage für alle Suchbegriffe. Notiz-/Dateizeiten schwanken in diesen kleinen Stichproben.

Host-CPU höchstens 16,16 %, verfügbarer RAM mindestens 5.048,1 MiB; Temperatur höchstens 59,5 °C einschließlich Baseline nach den nativen Prüfungen, I/O-Wartezeit höchstens 0,06 %. Kein Ressourcenengpass unter dieser Last. Pi-internes HTTP, WLAN/TLS-/Browser-Latenz und umfangreiche OCR-/KI-Jobs sind nicht Teil dieser HTTP-Zeitmessung; HTTPS wurde separat funktional geprüft.

Der Offline-Abgleich der **tatsächlich laufenden** Images, Go-Metadaten und aktualisierten Host-Pakete bestätigt null High-/Critical-Treffer mit veröffentlichtem Fix. Ungefixte/Hersteller-ignorierte und verbleibende Hinweise niedrigerer Priorität werden weiterhin ausgewiesen. Das ist eine Scanner-Zählung, keine Zahl nachgewiesener Exploits.

Die abschließende Bridge-Prüfung bestätigt weiterhin `01d1c53` und alle laufenden/gesunden Dienste. Der Scan-Tasten-Poller ist aktiv, der Canon LiDE 400 wird erkannt und der USB-Energiezustand bleibt aktiv. Ein Pi-Neustart wurde nicht durchgeführt.
