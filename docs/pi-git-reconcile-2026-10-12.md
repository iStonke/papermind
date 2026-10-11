# Pi-Git-Abgleich: erfolgreich abgeschlossen am 12. Oktober 2026

Der Snapshot-Rollout hatte den Git-HEAD auf dem Pi bei `fb57d08` belassen. Deshalb meldete `scripts/deploy_pi.sh --prod` lokale Änderungen und beendete sich vor Git-Update und Container-Build. Der ausdrücklich freigegebene feste Abgleich ist am 12. Oktober um **01:03:12 MESZ** erfolgreich abgeschlossen: Pi-Git-HEAD `20e59e1`, keine versionierten Änderungen, alle Anwendungsdienste gesund. Die laufenden Container verwenden weiterhin den erfolgreich geprüften Snapshot `8a06de418d9b7d94b9c7f775a5734e0f87bc47884e2086815c1808d19afa2dff` mit Schema 113.

## Ausgeführter Abgleich

- Zielcommit `20e59e1e4c32d8e68117862e520dc1bf4e4da6f3` wurde auf `origin/feat/ki-chat-integration` veröffentlicht. Er enthält die vier Audit-Commits und sichert zusätzlich die bereits aktive lokale Notizkorrektur als eigenen Commit, damit das nächste Git-Deployment diese Funktion erhält.
- Runner: `scripts/pi_git_reconcile.py`; festes Manifest: `scripts/pi_git_reconcile.json`, SHA-256 `247e613777558b951013f566eb8ddfe2f40301ce5ef711a42cb36a9b4bad887c`.
- Ausdrücklich freigegebene und installierte Bridge-Aktionen: `git_reconcile_status` und `git_reconcile`. Keine freie Auswahl von Host, Pfad, Branch, Commit oder Kommando. Der lokale Installer `scripts/install_pi_git_reconcile_bridge.py` prüft zusätzlich den festen Runner-SHA-256 `686372ef84b2b8684ebfa88ba948f11b7d87e9f8ed453436d44aa3ff91586d7f`.
- Vor jeder Änderung werden installierter Snapshot, aktueller Git-HEAD, Branch, leerer Staging-Bereich und die bekannten Hashes aller 127 betroffenen Quelldateien geprüft. Unbekannte Änderungen oder Symlinks führen zum Abbruch. Der Zielcommit muss im festen Origin-Branch enthalten sein.
- Die bisherigen Quelldateien werden mit SHA-256-Manifest und Dateirechten unter `.runtime/pi-git-reconcile` gesichert. Verzeichnisse sind auf 0700, Sicherungsdateien auf 0600 beschränkt.
- Bekannte Quelldifferenzen werden auf den Zielstand gebracht; Git-Branch und Index übernehmen diesen Stand. Dateiinodes bleiben erhalten, insbesondere Caddys einzelner Dateimount. Bei einem Fehler erfolgt eine kontrollierte Rücknahme, sofern keine konkurrierende Änderung erkannt wurde. Die Sicherung bleibt erhalten.
- Anwendung, Datenbank, Dokumentenspeicher, echte Umgebungsdateien und Scannerkonfiguration werden durch diesen Abgleich nicht umgestellt. Er baut und startet keine Container und führt keinen Pi-Neustart aus.

Die tatsächliche Vorprüfung bestätigte **100 geänderte versionierte Dateien** aus dem bekannten Snapshot und keine unbekannten Abweichungen. Der Abgleich bestätigte die 127 fest hinterlegten Zielquellen, aktualisierte 15 Quelldateien und übernahm Git-Branch und Index. Die anschließende unabhängige Statusabfrage bestätigt Ziel-HEAD und einen leeren versionierten Diff.

Quellsicherung auf dem Pi: `/home/jan/papermind/.runtime/pi-git-reconcile/20261011T230312966801-20e59e1e4c32`, einschließlich SHA-256-Manifest. Die bisherigen lokalen Quellstände bleiben dort erhalten. Die vorherige Mac-Bridge wurde als `papermind-pi-bridge.py.before-git-reconcile.bak` gesichert.

## Prüfung

- Vollständiger bestehender Quellstand einschließlich Notizkorrektur: 620 Backend-Tests und 32 Subtests, 692 Frontend-Tests sowie Produktionsbuild mit Größenbudgets erfolgreich.
- Zehn Git-Abgleich-Tests: Sicherung, Erhalt der aktiven Funktion und privater Dateien, Caddy-Inode, idempotente Wiederholung, unbekannte/staged/gelöschte Änderungen, Symlinks, falsche Release-/Zielidentität und Rücknahme bei fehlgeschlagener Indexaktualisierung.
- Alle 23 Standardbibliothek-Tests für Git-Abgleich und Rollout bestanden.
- Vollständiger lokaler Nachbau des tatsächlichen Snapshots über einer Git-Kopie bei `fb57d08`: 100 geänderte versionierte Dateien erfolgreich abgeglichen; danach kein versionierter Unterschied. Caddy-Inode und synthetische private Umgebungsdatei bleiben erhalten. Der Pi wurde dabei nicht verändert.

## Weiteres Deployment

Der Nutzer hat beide festen Bridge-Aktionen und die Veröffentlichung der aktiven Notizkorrektur ausdrücklich freigegeben. `AGENTS.md`, `CLAUDE.md` und der Bridge-Client enthalten die ergänzte Zugriffsliste. Der normale Aufruf `./scripts/deploy_pi.sh --prod` kann nun seine Git-Prüfung passieren. Die Abgleich-Werkzeuge und Protokolle folgen in einem separaten Commit; der normale Git-Deploy lädt diesen ebenfalls vom Origin-Branch.
