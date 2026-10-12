# Sicherheitsrelease vom 12. Oktober 2026

## Stand

Der Nutzer hat die Umsetzung der priorisierten Updates, den kontrollierten Pi-Rollout, die gezielte Suchoptimierung sowie die anschließende Bereinigung und den Betrieb ohne Root beauftragt. **Der Release ist lokal geprüft; Staging und Rollout auf dem Pi stehen noch aus.** Host-Patches werden separat vorbereitet und angewendet. Ein Pi-Neustart ist nicht freigegeben.

## Geprüfte Änderung

- Backend/Worker: gepinnte Python-3.12.15-/Debian-13-Basis, aktuelle Systempakete und Ghostscript mindestens `10.05.1~dfsg-1+deb13u3`. Der Build verweigert einen älteren Ghostscript-Stand.
- Frontend: nginx `1.30.5` mit aktualisierten Alpine-Paketen; Build mit Node 24. Die kopierten Assets übernehmen keine Root-Eigentümer. nginx schreibt PID und temporäre Dateien nach `/tmp`.
- Caddy: `2.11.7`, aus Standardmodulen mit Go `1.27.2` gebaut. Go-Modulversionen und Prüfsummen sind festgehalten; Netzwerk-/Crypto-/gRPC-/Telemetry-Module erfüllen die überprüften Fixstände. Buildparallelität ist auf zwei begrenzt. Offizielle Basisimages sind per Multiarch-Digest gepinnt.
- DB: PostgreSQL `17.11`, pgvector-Basis `0.8.7`, weiterhin Debian 12 und PostgreSQL-Hauptversion 17. SQL-Erweiterungen werden nicht automatisch aktualisiert. Der Runner prüft Erweiterungen, logische Plugins, Kollationsstand und den Vektoroperator vor/nach dem Wechsel. [PostgreSQL nennt die Voraussetzungen des Minor-Updates](https://www.postgresql.org/docs/17/release-17-11.html).
- Alle Produktionsdienste laufen mit UID 1000 beziehungsweise PostgreSQL mit UID 999, ohne effektive Linux-Capabilities und mit `no-new-privileges`. UID 1000 entspricht den vorhandenen privaten Schlüssel-, Scanner- und Steuerungs-Mounts. Benötigte Volume-Eigentümer werden erst nach Sicherung und Schreibsperre migriert; bisherige UID/GID/Modi werden privat für den Rückfall gesichert. Die TLS-CA-Prüfsumme muss erhalten bleiben.
- Docker-Kontexte schließen `.env`-Dateien, Laufzeitdaten, Git-Verzeichnisse und Schlüsseldateien aus.

Der lokale Offline-Abgleich der sechs neuen Images und ihrer Go-Metadaten findet **keine High-/Critical-Treffer mit veröffentlichtem Fix**. Ungefixte/Hersteller-ignorierte Debian-Treffer sowie wenige Alpine-Hinweise bleiben bestehen. Ein Go-Hinweis ohne bekannten Fix betrifft [GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932); die Prüfung ist ein Versionsabgleich, kein Nachweis erreichbarer Funktionen. Es wird kein vollständig schwachstellenfreies System behauptet. Vor dem Pi-Wechsel müssen dessen tatsächlich gebaute Paketbestände mit den überprüften Versionen übereinstimmen und separat lokal abgeglichen werden.

## Suchoptimierung

Die feste lesende Produktionsmessung bestätigt den Engpass: für „Rechnung“ insgesamt 147,8 ms Servicezeit, Hauptabfrage 108,6 ms; Auswahl/Sortierung etwa 7,3 ms. Für „Test“ waren es 210,7 ms Servicezeit und 157,4 ms Hauptabfrage. Die Treffertexte (`ts_headline`) beanspruchen den größten Teil. Der Suchbegriff ohne Treffer benötigte 17,0 ms. Pläne enthalten nur Knotentypen, öffentliche Schema-/Indexnamen und Zahlen; keine Dokumenttexte oder IDs.

Der neue Cache speichert ausschließlich kurze Treffertexte für bereits mit Owner-Scope/RLS gelesene Resultatzeilen. Schlüssel: Besitzer, Dokument, Änderungszeit, Suchbegriff und Sprach-/Headline-Konfiguration. Änderungszeiten werden von der bestehenden DB-Triggerfunktion gesetzt. Höchstens 512 Einträge, 120 Sekunden TTL, maximal 8 KiB je gecachtem Text. Große Texte bleiben ungecacht. Ranking, Sortierung, Filter und Gesamtzahl bleiben DB-Abfragen. Tests bestätigen identische wiederholte Treffer, sofortige Invalidierung nach gespeicherter Textänderung und fehlenden Zugriff eines anderen Kontos. Eine neue Pi-HTTP-Messreihe nach dem Rollout muss den tatsächlichen Effekt bestätigen; kalte Suchen benötigen weiterhin die Treffertext-Erzeugung.

## Alte PDF-Versionen

Der Worker prüft stündlich bekannte generierte Versionsnamen in kanonischen Dokumentverzeichnissen. Er entfernt höchstens 100 mindestens 14 Tage alte, vollständig unreferenzierte PDF-/Thumbnail-Dateien. Aktuelle `DocumentFile`- und `storage_key`-Referenzen werden erhalten, auch aus anderen Dokumenten und dem Papierkorb. Aktive Jobs, gesperrte Dokumente, Symlinks, unbekannte Dateinamen und frische Dateien werden ausgelassen. Schreib-/Wartungssperren sowie Dokument-Row-Locks sichern Publikation und Backup ab. Der Lauf hat zusätzlich ein Zeit-/Inspektionsbudget. Die Bereinigung löscht keine sichtbaren Dokumente.

## Validierung vor dem Pi-Staging

- **631 Backend-Tests und 32 zusätzliche Subtests** bestanden, auch gegen das neue PostgreSQL-17.11-Image mit UID 999 und ohne Capabilities; alle Migrationen bis 113. Keine übersprungenen Tests. Sechs bestehende Bibliotheks-/Test-Warnungen.
- **692 Frontend-Tests** mit Node 24, Produktionsbuild und Größenbudgets bestanden; `npm audit` ohne bekannte Schwachstellen.
- **45 Skript-Tests** einschließlich Sicherungsreihenfolge, Abbruch vor Änderungen, Eigentümer-/Git-Rückfall und eingeschränkter Argumente bestanden.
- Rootloses Backend und Worker: synthetisches großes PDF, Thumbnail, native OCR, durchsuchbares OCRmyPDF und Piper erfolgreich. Rootloser nginx: Gesundheit und HTTP 401 für anonymen API-Zugriff. Vollständiger rootloser TLS-Proxy Caddy → nginx → Backend: HTTP 200.
- Bestehende produktive Container wurden während der lokalen Prüfung nicht gewechselt. Frühere Diagnose-/Rollout-Aktionen behalten ihre ursprünglichen Bindungen.

## Kontrollierter Wechsel

Die neue feste Bridge bereitet ausschließlich diesen Release vor. Sie prüft `acc22ca`, saubere Quellen und gesunde Container, baut die Kandidaten separat und ermöglicht deren Paketabgleich. Der eigentliche Wechsel benötigt einen erfolgreichen frischen verschlüsselten NAS-Backup-Lauf und die Prüfung sämtlicher Artefakt-Hashes und Manifest-HMAC. Danach folgen Schreibsperre, Stoppen der App-Dienste, gesicherter Eigentümerwechsel, fester Git-Fast-Forward und Containerwechsel. Bei Fehlern werden die ursprünglichen Images, Eigentümer und Git-Revision wiederhergestellt. Keine frei wählbaren Refs, Hosts, Images, Shelltexte oder echten `.env`-Änderungen; kein Pi-Neustart.

Nach dem Wechsel werden UID/Capabilities, RLS, native PDF/OCR/Piper-Funktionen, Paketbestände, bestehende TLS-CA und begrenzte HTTP-Last erneut geprüft. Anschließend folgen die festen Host-Sicherheitsupdates und eine Scanner-/Dienstprüfung. Das Ergebnis dieses Abschnitts wird nach Abschluss ergänzt.
