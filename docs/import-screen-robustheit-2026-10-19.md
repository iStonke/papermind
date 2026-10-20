**Import-Screen: Robustheit, Scanablauf, KI-Analyse und Formularverhalten**

Codeanalyse vom 19. Oktober 2026 auf dem lokalen Branch `feat/ki-chat-integration`, ergänzt um den bereitgestellten Screenshot. Dieses Dokument enthält Befunde und einen priorisierten Umsetzungsvorschlag. P0 bezeichnet hier die erste Umsetzungsgruppe wegen möglicher Seitenverluste oder inkonsistenter Importergebnisse; P1 die anschließenden Funktionskorrekturen; P2 weitere Qualitäts- und Komfortverbesserungen.

**Ausgangsbefunde vor der Umsetzung**

Die folgenden Codebelege und Zeilenangaben dokumentieren die Ausgangsanalyse; die Umsetzung ist am Ende dieses Dokuments zusammengefasst.

| Priorität | Befund | Auswirkung | Codebeleg |
| --- | --- | --- | --- |
| P0 | „Auswahl importieren“ entfernt zuerst alle nicht ausgewählten Seiten und ruft erst danach den eigentlichen Import auf. Bei Inbox-Quellen wird die Quelldatei dabei serverseitig verändert. | Nicht ausgewählte Seiten können verschwinden, obwohl Pflichtfelder fehlen oder der Import anschließend scheitert. | [Auswahlimport](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1908), [Seitenentfernung](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:4324) |
| P0 | Bei einem Teilerfolg bleiben die eingereichten Dokumente im Dialog. Die Antwort liefert keine stabile Zuordnung zwischen Staging-Dokument und erfolgreichem Ergebnis. | Ein erneuter Versuch reicht auch bereits erfolgreiche Dokumente wieder ein. Die vorhandene SHA-256-Dublettenprüfung kann identische Dateien abweisen, ersetzt aber keine verlässliche Wiederaufnahme des Importauftrags. | [Commit im Frontend](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:5481), [Commit-Service](/Users/admin/Documents/paperMind/backend/app/services/import_staging.py:2483) |
| P0 | Der nachgereichte Screenshot zeigt „Could not apply selected color mode“. Dieser Fehler wird beim Zusammenstellen des endgültigen PDFs ausgelöst, wenn die Graustufen-/S/W-Konvertierung kein Ergebnis liefert. Graustufen sind bereits die Frontend-Voreinstellung. Der Konvertierungshelfer fasst unterschiedliche Ursachen als `None` zusammen. | Ein normaler Import kann auch ohne ausdrückliche Farbwahl scheitern. Aus der Oberfläche ist weder die betroffene Seite noch der konkrete Grund erkennbar. Der Screenshot allein belegt keine bestimmte Ursache wie Speichermangel oder Zeitüberschreitung. | [Fehlerstelle](/Users/admin/Documents/paperMind/backend/app/services/import_staging.py:2331), [Konvertierungshelfer](/Users/admin/Documents/paperMind/backend/app/services/ocr_pipeline.py:768), [Voreinstellung](/Users/admin/Documents/paperMind/frontend/src/stores/importStaging.js:111) |
| P1 | Die Betreffheuristik gibt „Ohne Betreff“ zurück. Dieser nicht leere Text bleibt bei der Normalisierung erhalten. Zusätzlich setzt die Titelbildung bei fehlendem Thema explizit diesen Ersatzwert. | Ein fehlendes Ergebnis wird zu einem vermeintlichen Titelvorschlag. Über die Heuristik kann es sogar als reguläres Ergebnis gelten, weil `used_fallback` nur auf einen leeren Betreff prüft. | [Heuristik](/Users/admin/Documents/paperMind/backend/app/services/import_metadata_heuristics.py:139), [Titelbildung](/Users/admin/Documents/paperMind/backend/app/services/import_staging.py:1859), [Fallback-Kennzeichnung](/Users/admin/Documents/paperMind/backend/app/services/import_staging.py:1892) |
| P1 | Die Sichtbarkeit des Übernahmechips verlangt nur einen nicht leeren, abweichenden Vorschlag mit Status `ready`. Der Chip beschriftet auch Ersatzwerte pauschal mit „übernehmen“. | „Ohne Betreff übernehmen“ wird angeboten, obwohl der bereits eingegebene Name aussagekräftiger ist. | [Chip](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:650), [Sichtbarkeitsprüfung](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1510) |
| P1 | Eine Kategorie wird gesetzt, wenn sie unberührt **oder leer** ist. Bei Korrespondent und Tags liegen zwischen der Prüfung auf manuelle Bearbeitung und dem Schreiben asynchrone Ladevorgänge. | Bewusstes Leeren kann rückgängig gemacht werden; Eingaben während einer laufenden Anfrage sind nicht durchgängig geschützt. Auch das explizite Übernehmen eines Titels markiert ihn nicht als manuell geschützt. | [Ergebnisanwendung](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:3425), [Übernahme](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:3811) |
| P1 | Der KI-Gesamtstatus wird bereits bei einem automatisch gefüllten Feld als `success` berechnet, vor der Prüfung auf laufende oder fehlgeschlagene Arbeit. Der Importknopf prüft weder `scannerActive` noch direkt die laufende Scanbereinigung. | Inhaltliche Teilergebnisse und tatsächlicher Abschluss werden vermischt. Ein Import kann unter bestimmten Zuständen bereits freigegeben sein, während weitere Vorbereitung läuft. | [KI-Status](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1969), [Importfreigabe](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1705) |
| P1 | Die Analyse erhält Quelldatei-IDs und einen Umfang, jedoch keine aktuellen Seitenreferenzen samt Reihenfolge und Rotation. Neue Seiten lösen bei bereits fertigem Ergebnis nicht zuverlässig eine neue Dokumentanalyse aus. | Ergebnisse können sich auf die ursprüngliche erste Seite oder eine überholte Dokumentzusammensetzung beziehen. Bei mehreren Scanquellen werden einzelne Quellenanalysen auf dasselbe Staging-Dokument angewendet. | [Analyseanfrage](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:3636), [Anfrageschema](/Users/admin/Documents/paperMind/backend/app/schemas/import_staging.py:225), [Quellenanwendung](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:3223) |
| P1 | „Analyse wiederholen“ verwendet denselben Endpoint; bei einer einzelnen Quelle kann dieser unmittelbar das bisherige Cache-Ergebnis zurückliefern. | Ein Wiederholen garantiert keine neue OCR- oder KI-Auswertung. | [Wiederholen](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:3775), [Cache-Rückgabe](/Users/admin/Documents/paperMind/backend/app/services/import_staging.py:1932) |
| P1 | Die Formularwerte und Bearbeitungskennzeichen sind überwiegend dialogweit. Zusätzliche Metadaten werden beim Commit nur an das erste Dokument angehängt. | Bei mehreren Dokumenten fehlt eine durchgängige Bearbeitung und Validierung pro Dokument. | [Formularzustand](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1163), [Primärdokument](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:1627), [Commit-Zuordnung](/Users/admin/Documents/paperMind/frontend/src/components/ImportStagingDialog.vue:5501) |

Die Befunde beschreiben den geprüften lokalen Code. Die genaue Abfolge des fotografierten Scanvorgangs lässt sich ohne dessen Laufzeitdaten nicht rückwirkend feststellen. Der sichtbare Vorschlag passt jedoch unmittelbar zu den beschriebenen Ersatzwert- und Anzeigewegen.

**1. Vorschläge und manuelle Eingaben zuverlässig behandeln — P1**

1. **Fehlende Ergebnisse als fehlend speichern.** `null`, Leerraum und Texte wie „Ohne Betreff“, „Unbekannt“ oder „nicht erkannt“ dürfen keine inhaltlichen Betreffwerte werden. Diese Prüfung gehört in Backend und Frontend, damit auch ältere Cache-Ergebnisse korrekt dargestellt werden.
2. **Übernehmen nur für einen verwertbaren Unterschied anbieten.** Vorschläge nach Normalisierung mit dem aktuellen Feld vergleichen. Identische Texte, bloß andere Leerzeichen und reine Ersatzwerte ausblenden. Bei einem vorhandenen Namen einen echten Änderungsvorschlag zeigen, keine automatisch angebotene Verschlechterung.
3. **Dateiname und erkanntes Thema auseinanderhalten.** Für die interne Speicherung kann eine neutrale Benennung erforderlich sein. Sie darf nicht als von der KI erkanntes Thema erscheinen. Ein nicht erkanntes Thema benötigt höchstens einen Hinweis „Kein verlässlicher Titel erkannt“.
4. **Manuelle Entscheidungen pro Feld schützen.** Tippen, Löschen, Auswählen, Übernehmen und Verwerfen erhöhen eine Feldrevision. Ein verspätetes Ergebnis darf nur den Stand verändern, auf dessen Revision es beruht. Dies auch nach jedem asynchronen Ladeschritt erneut prüfen.
5. **Bewusst geleert von noch unbekannt unterscheiden.** Ein vom Benutzer entferntes Datum, ein gelöschter Dokumenttyp oder ein abgelehntes Tag bleiben entfernt. Dafür reicht ein Vergleich auf einen leeren Wert nicht aus.
6. **Herkunft dauerhaft erkennbar machen.** Je Feld zwischen manuell, Regel, OCR und KI unterscheiden. Eine kurze Animation allein vermittelt die Herkunft nach einigen Sekunden nicht mehr. Unsichere Werte als prüfbedürftig kennzeichnen; keine unbegründet präzisen Prozentwerte anzeigen.
7. **Änderungsvorschläge kontrollierbar halten.** Bei bereits bearbeiteten Feldern den neuen Vorschlag neben dem bestehenden Wert anbieten. Übernehmen, Verwerfen und Rückgängig machen ermöglichen; verworfene identische Vorschläge nicht bei jedem Inbox-Ereignis erneut einblenden.

**2. Verhalten der Dokumentendetailschublade übernehmen — P1**

Die Detailschublade ist die passende Referenz. Gemeinsame Feldkomponenten und Hilfsfunktionen verhindern, dass beide Ansichten weiter auseinanderlaufen. Im Import werden Änderungen im Entwurf gehalten und mit „Importieren“ endgültig übernommen; Fokuswechsel und Auswahl sollen sich trotzdem gleich anfühlen.

| Feld | Derzeitiger Unterschied | Empfohlenes Verhalten im Import |
| --- | --- | --- |
| Dokumentname | Zweizeiliges, festes Textfeld ohne die 200-Zeichen-Grenze der Detailschublade. | Gleiche kompakte Darstellung, Fokus-/Hoverzustände und maximale Länge. Normalisierung bei Verlassen des Felds, klarer Fehler bei fehlendem Namen. |
| Datum | Eigene starre Prüfung und Eingabemaske; keine sichtbare Feldfehlermeldung. | Gemeinsamen Parser aus `dates.js` verwenden. `1.2.2026` ebenso wie `01.02.2026` akzeptieren, bei Blur normalisieren, Kalenderfehler direkt anzeigen. Eingabe in der Mitte ohne springenden Cursor ermöglichen. |
| Dokumenttyp | Eigenes Select; KI-Werte außerhalb des zentralen Vokabulars werden ergänzt. | Gleiche Optionen und Menügestaltung; unbekannte Werte als Vorschlag zur Zuordnung behandeln. Bewusstes Leeren respektieren und Verwaltung über dieselbe Aktion erreichbar machen. |
| Korrespondent | Freie Combobox mit automatischer Anlage beim Import; Detailschublade wählt vorhandene Einträge. | Suchbares Autocomplete mit vorhandenen Einträgen, Kurzname und Sammlungskennzeichnung. Unbekannte KI-Absender separat zur Zuordnung anbieten. Eine Neuanlage braucht eine ausdrücklich erkennbare Aktion. |
| Tags | Eigene Combobox mit anderer Chip- und Tastaturbedienung. | Den vorhandenen `TagInlineEditor` verwenden; identisches Hinzufügen, Entfernen, Vorschlagsmenü und Verhalten bei Enter, Pfeiltasten, Escape und Backspace. Neue Tags sichtbar als solche behandeln. |
| Notizen | Unterschiedliche Feldausprägung und Längenbegrenzungen zwischen Import und Detailbearbeitung. | Gemeinsames Verhalten mit wachsendem Textfeld. Zulässige Länge zwischen Oberfläche und Backend abstimmen und eine KI-Zusammenfassung als solche erkennbar halten. |
| Aufbewahrung | Eigenes Formular neben dem Statusleistenverhalten der Detailschublade. | Gleiche Begriffe und Statusdarstellung für Vorschlag, akzeptiert und manuell. Die Entscheidung bei erneuter Analyse schützen. |

Referenzen: [Detailschublade](/Users/admin/Documents/paperMind/frontend/src/views/DocumentsWorkspace.vue:1550), [TagInlineEditor](/Users/admin/Documents/paperMind/frontend/src/components/TagInlineEditor.vue:1), [Datumsparser](/Users/admin/Documents/paperMind/frontend/src/utils/dates.js:42).

8. **Feldfehler erklären.** Pflichtfelder sichtbar markieren und beim Importversuch die erste problematische Stelle fokussieren. Neben einem deaktivierten Importknopf den konkreten Grund nennen.
9. **Pflichtangaben fachlich reduzieren.** Derzeit verlangt die Oberfläche Name, Datum, Dokumenttyp und mindestens ein Tag, während das Commit-Schema Datum, Typ und Tags optional zulässt. Empfehlung: Seiten und ein brauchbarer Name als Basis; fehlendes Datum, fehlender Typ und fehlende Tags als offene Angaben behandeln. Unbekannte Informationen sollen nicht durch erfundene Werte ersetzt werden müssen.
10. **Tastatur- und Fokusverhalten vereinheitlichen.** Gleiche Tabreihenfolge und Shortcuts; Escape schließt zuerst das geöffnete Menü. Verknüpfte Feldlabels, benannte Symbolschaltflächen, sichtbarer Tastaturfokus und verständliche Statusmeldungen ergänzen.

**3. Scanablauf und Seitenbearbeitung absichern — P0/P1**

11. **Auswahlimport ohne vorheriges Löschen umsetzen — P0.** Ausgewählte Seiten als gesonderten Importauftrag senden. Nicht ausgewählte Seiten bleiben im Entwurf erhalten. Erst nach bestätigtem Erfolg die tatsächlich importierten Seiten als erledigt markieren. Das Entfernen darf keine Voraussetzung für das Importieren sein.
12. **Scanende und Importgrenze eindeutig machen.** Beim aktiven Scan „Weitere Seite“ und „Scannen abschließen“ deutlich unterscheiden. Vor dem Commit die zu importierenden Seiten und ihre Fassungen festhalten. Später eintreffende Seiten eindeutig dem verbleibenden oder einem neuen Entwurf zuordnen.
13. **Einzelne Phasen anzeigen.** „Scanner wartet“, „Seite wird gescannt“, „Scan wird übertragen“, „Seite wird verbessert“, „Text wird erkannt“ und „Metadaten werden analysiert“ getrennt führen. Prozentwerte nur für den tatsächlich messbaren Vorgang zeigen; ein vollständig erfasstes Blatt bedeutet noch keinen abgeschlossenen Import.
14. **Fehler an der betroffenen Seite oder Sitzung anzeigen.** Offline, Zeitüberschreitung, fehlende Datei und Verarbeitungsfehler sind bereits als Fehlerarten vorhanden. Ergänzend zur Benachrichtigung einen beständigen Hinweis mit passender Wiederholungsaktion anbieten. Bereits eingetroffene Seiten bleiben erhalten.
15. **Abbruch bestätigen lassen.** „Abbruch angefordert“ bis zur Bestätigung der Ausführung anzeigen. Zwischen „aktuellen Scan abbrechen“ und „gesamten Entwurf verwerfen“ unterscheiden. Eine neue Scananforderung erst zulassen, wenn der Gerätezustand dies erlaubt.
16. **Scanbefehle auch serverseitig gegen Wiederholung schützen.** Doppelklicks und Wiederholungen nach Verbindungsabbruch dürfen keinen zweiten identischen Scanauftrag erzeugen. Bei mehreren berechtigten Nutzern muss die Belegung des Geräts nachvollziehbar sein.
17. **Seitenqualität prüfbar machen.** Vermutlich leere, stark schiefe, abgeschnittene oder schlecht lesbare Seiten markieren. Leerseiten zuerst zur Entfernung vorschlagen; empfindliche automatische Löschungen vermeiden. Neu scannen und eine gezielte Seite ersetzen ermöglichen.
18. **Original und Bereinigung nachvollziehbar vergleichen.** Original, Graustufen und Farbe verständlich benennen. Beschnitt, Drehung und Farbwahl in Vorschau und endgültigem PDF müssen übereinstimmen. Eine Bereinigung darf spätere manuelle Entscheidungen nicht zurücksetzen.
19. **Seitenaktionen rückgängig machen können.** Löschen, Umordnen, Drehen, Ersetzen und Aufteilen im Entwurf reversibel halten. Mehrere Dokumente in einer Scansitzung ausdrücklich trennen können.

**4. OCR und KI auf dem aktuellen Dokument ausführen — P1/P2**

20. **Dokumentrevision als Analysegrundlage verwenden — P1.** Quellen, ausgewählte Seiten, Reihenfolge, Drehung und relevante Bereinigungsfassung bilden eine Revision. Analyseanfragen und Antworten tragen diese Revision; überholte Ergebnisse werden nicht mehr angewendet.
21. **Mehrseitige Dokumente zusammenhängend auswerten.** Einzelanalysen neuer Scanseiten dürfen den Titel des gesamten Dokuments nicht nacheinander durch Seitenthemen ersetzen. Eine schnelle Vorschau auf der ersten Seite ist sinnvoll, danach folgt eine konsolidierte Dokumentanalyse.
22. **Analyseumfang ehrlich benennen.** Der aktuelle Modus `all_pages` bleibt begrenzt: eingebetteter Text wird aus höchstens fünf Seiten gelesen; beim OCR-Fallback gelten höchstens zwei Quellen mit jeweils drei Seiten. Den tatsächlich untersuchten Umfang anzeigen und bei Bedarf gezielt erweitern, ohne den Pi unkontrolliert zu belasten.
23. **Textqualität vor Textmenge prüfen.** Eine vorhandene, aber unbrauchbare PDF-Textschicht darf bessere OCR nicht verhindern. Bei mehreren OCR-Versuchen ist die längste Zeichenfolge nicht zwingend die beste. Lesbarkeit, plausible Wörter und erkennbare Dokumentstruktur berücksichtigen.
24. **Zeilen und Kopfbereich erhalten.** Der OCR-Fallback glättet Zeilenumbrüche, während Absender- und Betreffheuristiken auf Zeilenstruktur angewiesen sind. Rohtext und normalisierte Suchfassung getrennt halten; Kopf, Betreff und Haupttext für die Extraktion priorisieren.
25. **Prompt-Kontext sinnvoll verteilen.** Der Standardkontext ist knapp; die Auswahl wird anschließend wieder in Dokumentreihenfolge abgeschnitten. Dadurch können wichtige spätere Textstellen trotz hoher Bewertung entfallen. Ein festes Budget für Kopf/Betreff, Kernaussage, Datum und gegebenenfalls Beträge vorsehen.
26. **Datumsrollen unterscheiden.** Ausstellungsdatum, Eingangsdatum, Leistungszeitraum und Frist getrennt bewerten. Alte Dokumente vor 1990 und zukünftige Datierungen werden derzeit pauschal verworfen. Ungewöhnliche Datierungen besser sichtbar zur Prüfung anbieten, statt sie still zu verlieren.
27. **Ergebnisfelder einzeln validieren.** Das JSON-Format ist bereits aktiviert, aber konkrete Feldtypen, erlaubte Werte, Textlängen und fehlende Werte benötigen ein strenges Antwortschema und nachgelagerte Plausibilitätsregeln. Ein problematisches Feld soll nicht alle brauchbaren Ergebnisse entwerten.
28. **Quellenbelege für prüfbedürftige Werte anbieten.** Bei Datum, Absender und Thema eine Fundstelle oder einen Textausschnitt anzeigen. Bei widersprüchlichen Daten eine Auswahl ermöglichen. Die Zusammenfassung darf keine Fristen, Beträge oder Verpflichtungen ergänzen, die im Dokument nicht belegt sind.
29. **Dokumentinhalt ausdrücklich als Daten behandeln.** Eingescannte Handlungsanweisungen dürfen die Regeln der Metadatenextraktion nicht ersetzen. OCR-Inhalt klar abgrenzen, das erlaubte Antwortformat festlegen und ausgegebene Werte weiterhin unabhängig validieren.
30. **Wiederholungsaktionen unterscheiden.** „Ergebnisse aktualisieren“ liest den vorhandenen Stand; „Neu analysieren“ erzeugt einen neuen Lauf; „Texterkennung wiederholen“ startet OCR erneut. Dabei manuelle Eingaben erhalten und gezielte Wiederholung einzelner Phasen ermöglichen.
31. **Cache fachlich versionieren.** Neben Quelle und Benutzer auch Quellenfassung, Dokumentrevision, Analyseumfang, Modell, Prompt und relevante Konfiguration berücksichtigen. Für jede neue Antwort eine eindeutige Ergebnisrevision verwenden; ein Zeitstempel mit Sekundengenauigkeit plus identischem Titel ist dafür zu schwach.
32. **Arbeitsstatus und Ergebnisqualität trennen.** Regeln können früh einen brauchbaren Wert liefern, während die KI noch läuft. Gleichzeitig „Metadaten teilweise erkannt“ und „KI-Analyse läuft“ darstellen können. Ein späterer Teilfehler bleibt sichtbar, ohne schon gewonnene Werte zu verwerfen.

**5. Importabschluss, Wiederaufnahme und Mehrfachimporte — P0/P1**

33. **Importaufträge wiederholungssicher machen — P0.** Eine stabile Auftrags-ID und Dokument-IDs zwischen Browser und Backend verwenden. Geht die Antwort nach erfolgreichem Speichern verloren, liefert die Wiederholung denselben Auftragsstand und reicht nicht blind alles neu ein.
34. **Teilerfolge einzeln abschließen — P0.** Erfolgreiche Staging-Dokumente als erledigt kennzeichnen und aus der offenen Auswahl nehmen. Fehlgeschlagene Dokumente mit ihren Eingaben und Seiten erhalten. Der nächste Versuch überträgt ausschließlich diese offenen Dokumente.
35. **Dokument und Metadaten als konsistenten Abschluss behandeln.** PDF, Typ, Korrespondent, Tags, Aufbewahrung und Hintergrundaufträge werden aktuell in mehreren Schritten gespeichert. Bei Fehlern nach dem Anlegen muss der Auftrag den bereits erreichten Stand kennen und gezielt fortsetzen oder kontrolliert zurückrollen können. Frühe Hintergrundjobs dürfen nicht mit unvollständigen Metadaten konkurrieren.
36. **Metadaten pro Dokument führen.** Jedes Dokument erhält seinen eigenen Entwurf, Bearbeitungsstand, Analysefortschritt und seine eigenen Fehler. Die rechte Spalte zeigt das ausgewählte Dokument. Gemeinsame Angaben können über eine bewusste Mehrfachaktion gesetzt werden.
37. **Entwürfe wiederherstellbar machen.** Ein Neuladen oder erneutes Anmelden soll vorhandene Scanquellen, Reihenfolge und bestätigte Eingaben wiederherstellen können. Entwürfe eindeutig dem Benutzer zuordnen; erledigte oder verworfene Entwürfe nicht automatisch erneut öffnen.
38. **Dubletten verständlich behandeln.** Die vorhandene Prüfsummenprüfung beibehalten. Wenn ein Dokument bereits vorhanden ist, die bestehende Ablage verlinken und den Vorgang als Dublettenentscheidung darstellen. Inhaltlich ähnliche Scans nur als mögliche Dublette kennzeichnen.
39. **Mehrere Dateien unabhängig rückmelden.** Ein defektes oder ungeeignetes PDF darf nicht den sichtbaren Fortschritt bereits gültiger Quellen verschlucken. Fehler pro Datei erklären, Größen-/Seitenlimits früh prüfen und passwortgeschützte PDFs verständlich behandeln.
40. **Erfolgstexte an den realen Stand binden.** „OCR läuft im Hintergrund“ nur anzeigen, wenn tatsächlich ein OCR-Auftrag erzeugt wurde. Seitenanzahl, Dokumentanzahl, noch laufende Verarbeitung und Ziel der Ablage eindeutig benennen.

**6. Bedienbarkeit, Leistung und Wartbarkeit — P1/P2**

41. **Vorschau und Eingabekontext verbinden.** Ausgewählte Seite und bearbeitetes Dokument klar hervorheben. Bei ausreichender Breite Formular und lesbare Vorschau zugleich nutzbar machen; auf schmalen Ansichten Auswahl und Scrollposition beim Wechsel erhalten.
42. **Fortschritt ohne Layoutsprünge zeigen.** Platz für Feldstatus und Vorschläge reservieren. Asynchrone Ergebnisse dürfen keine Eingabe, Cursorposition oder geöffnete Auswahl verschieben. Sichtbare Rückmeldungen auch ohne Animation und ohne reine Farbcodierung anbieten.
43. **Vorhandene Synchronisierung gezielt weiterverwenden.** SSE mit Polling-Fallback und die Serialisierung eintreffender Quellen existieren bereits. Analysefortschritt möglichst über denselben Ereignisweg aktualisieren; zusätzliches 1,5-Sekunden-Polling pro Dokument begrenzen und bei Inaktivität zurücknehmen. Schwerarbeit je Quelle und Revision zusammenfassen.
44. **Große Stapel schrittweise anzeigen.** Miniaturen zuerst für sichtbare Seiten laden, Speicher begrenzen und nicht benötigte Renderaufträge abbrechen. Fehlende Miniaturen sollen mit einer eigenen Wiederholungsaktion sichtbar bleiben, während der restliche Import weiter bedienbar ist.
45. **Fachlogik aus dem großen Dialog auslagern.** Der Dialog umfasst rund 7.600 Zeilen. Formularfelder, Scansteuerung, Seitenoperationen, Analysezustand und Commit-Verarbeitung in klar getrennte Komponenten bzw. Composables aufteilen. Einen gemeinsamen Metadateneditor für Import und Detailschublade verwenden.
46. **Diagnostik auf technische Ereignisse konzentrieren.** Zeiten, Phasen, Ergebnisrevision und strukturierte Fehlerarten protokollieren. Der Analysepfad schreibt derzeit auch OCR-Vorschauen und Modellantworten ins Log; Dokumenttexte aus routinemäßigen Produktionslogs entfernen und gezieltes Debugging ausdrücklich begrenzen.

**7. Farbkonvertierung beim Import zuverlässig ausführen — P0, nachgereichter Screenshot**

47. **Den Fehler „Could not apply selected color mode“ als eigenen Fehlerfall beheben.** Es genügt nicht, die englische Meldung zu übersetzen oder abzufangen. Die Umsetzung muss folgende Anforderungen erfüllen:

    - Den tatsächlichen Fehlergrund erhalten: belegt, Zeitlimit, Ressourcenlimit, unlesbare Quelle oder fehlgeschlagene Konvertierung. Die Konvertierung reicht diese strukturierte Ursache mit Seitenbezug weiter, statt alle Fehler als `None` zusammenzufassen. Technische Details gehören in die Diagnose; die Oberfläche erklärt die konkrete Handlung verständlich auf Deutsch.
    - Unnötige erneute Farbkonvertierung vermeiden, wenn die ausgewählte Fassung den gewünschten Modus bereits nachweislich besitzt. Insbesondere die automatische Graustufenvoreinstellung und schon bereinigte Scans aufeinander abstimmen.
    - Rendergröße und Speicherbedarf an die bestehenden Ressourcenlimits anpassen. Pro Seite verarbeiten und temporäre Ressourcen zuverlässig freigeben. Bei tatsächlich wiederholbaren Fehlern eine begrenzte Wiederholung mit angepassten Renderparametern vorsehen; dabei eine relevante Qualitätsänderung sichtbar machen. Die Ressourcenlimits nicht pauschal aufheben.
    - Während der Konvertierung eine feste Quellenfassung verwenden. Parallele Scanbereinigung, Seitentausch oder Seitenentfernung dürfen nicht dieselbe Quelle unbemerkt verändern.
    - Bei einem Fehler alle noch offenen Seiten, Formulareingaben und Farbentscheidungen erhalten. Der Benutzer kann gezielt erneut versuchen oder ausdrücklich eine andere verfügbare Fassung wählen. Original/Farbe nicht still anstelle der gewählten Graustufen speichern.
    - Vorschau und endgültiges PDF konsistent halten: Farbmodus, Beschnitt, Rotation, physische Seitengröße und Reihenfolge prüfen. Vorhandene Textschichten bei der Wahl des Konvertierungsverfahrens berücksichtigen und einen Verlust nicht beiläufig durch die Voreinstellung verursachen.
    - Regressionstests mit realistischen A4-Scans, großen Bildern, mehreren Seiten, Original, Graustufen, Farbe und dem weiter unterstützten S/W-Modus ergänzen. Unter den produktionsnahen Zeit-/Speichergrenzen auch Auslastung, Zeitüberschreitung, Bereinigungsüberschneidung und einen fehlgeschlagenen Wiederholungsversuch prüfen. Die bestehende Graustufenprobe mit einem 100×100-Pixel-Bild reicht für diese Fehlerklasse nicht aus.

**Empfohlene Umsetzung in drei Paketen**

1. **Datenintegrität und eindeutige Zustände:** Auswahlimport, Teilerfolge, wiederholbare Aufträge, Schutz manueller Eingaben, Dokumentrevisionen, korrekte Importfreigabe und zuverlässige Farbkonvertierung. Gleichzeitig den sichtbaren Ersatzwertfehler in Backend und Frontend beseitigen.
2. **Gemeinsame Formulare:** Metadateneditor mit denselben Datums-, Korrespondenten-, Tag- und Fokusregeln wie die Detailschublade; Metadaten pro Dokument; verständliche Pflichtfeld- und Statusmeldungen.
3. **Erkennungsqualität und Komfort:** konsolidierte Mehrseitenanalyse, bessere OCR-/Kontextauswahl, Belege für Vorschläge, Qualitätsprüfung, Wiederaufnahme und Leistung bei großen Stapeln.

**Konkrete Abnahmekriterien**

- Ein vorhandener aussagekräftiger Name erhält für `null`, Leerraum oder „Ohne Betreff“ keinen Übernahmechip. Das gilt auch für alte Cache-Ergebnisse.
- Ein manuell eingegebener oder ausdrücklich übernommener Titel bleibt bei einer späteren Workerantwort erhalten.
- Bewusst geleerte Felder bleiben nach erneuter Analyse leer. Änderungen während des Ladens von Tags oder Korrespondenten bleiben erhalten.
- „Auswahl importieren“ verändert keine nicht ausgewählte Seite, auch wenn Pflichtfelder fehlen, die Verbindung abbricht oder der Import fehlschlägt.
- Ein Teilerfolg mit zwei Dokumenten führt beim Wiederholen nur das noch offene Dokument aus.
- Geht eine erfolgreiche Commit-Antwort verloren, stellt das erneute Absenden den bisherigen Stand wieder her.
- Drehen, Entfernen, Ersetzen oder Umsortieren einer Seite macht überholte Analyseergebnisse unanwendbar.
- Weitere Scanseiten werden konsolidiert ausgewertet; eine Folgeseite ersetzt nicht ungefragt das Thema des ganzen Dokuments.
- „Neu analysieren“ erzeugt nachweislich einen neuen Lauf; „Ergebnisse aktualisieren“ darf den Cache verwenden.
- Ein bereits erkanntes Feld verdeckt weder eine noch laufende Phase noch einen Fehler einer anderen Phase.
- Datum, Tags, Korrespondent und Tastaturbedienung verhalten sich in Import und Detailschublade gleich.
- Scannerabbruch, Offlinezustand und Zeitüberschreitung sind sichtbar; bereits erfasste Seiten bleiben verfügbar.
- Gleichzeitige SSE- und Polling-Meldungen fügen dieselbe Quelle weiterhin nur einmal hinzu.
- Vorschau und exportiertes PDF besitzen dieselbe Reihenfolge, Drehung, Bereinigung und denselben Beschnitt.
- Ein normaler A4-Scan lässt sich mit der Graustufenvoreinstellung innerhalb der produktionsnahen Ressourcenlimits importieren; dies gilt auch für einen mehrseitigen Stapel.
- Ein vorübergehend belegter Konvertierungsprozess oder eine laufende Bereinigung führt zu einem nachvollziehbaren Warte-/Wiederholungszustand und erhält den vollständigen Entwurf.
- Ein endgültiger Konvertierungsfehler zeigt eine verständliche deutsche Meldung mit betroffener Seite und passenden Aktionen. Es gibt weder einen stillen Wechsel des Farbmodus noch eine Erfolgsmeldung für ein unvollständiges Dokument.

**Durchgeführte Prüfung und Grenzen**

Zehn vorhandene Frontendtests aus `importStagingDialog`, `importStagingStore`, `documentMetadata` und `scannerLivePreview` sind erfolgreich. Die vorhandenen Tests decken die hier beschriebenen problematischen Verhaltensfolgen nicht ausreichend ab.

Zusätzlich wurden die tatsächlichen Funktionen isoliert mit synthetischen Eingaben ausgeführt: Ein als Fallback markiertes „Ohne Betreff“ besteht die Anzeigeprüfung; ein Dokument im Analysestatus `working` wird bei bereits automatisch gefülltem Titel als `success` berechnet; der Auswahlimport ruft die Entfernung nicht ausgewählter Seiten vor dem Commit auf; die Themenheuristik erzeugt für ein unbekanntes Thema den Ersatzwert „Ohne Betreff“.

Die isolierten Prüfungen ersetzen keine Browser- oder Hardwaretests. Die Backend-Testsuite wurde nicht ausgeführt, weil im verfügbaren Host-Python die Projektabhängigkeit SQLAlchemy fehlt. Diese Einschränkung beschreibt die Ausgangsanalyse. Die danach durchgeführte Umsetzung und ihre Prüfungen sind nachfolgend dokumentiert.


**Umsetzung im lokalen Quellstand**

Die Verbesserungsliste wurde als zusammenhängender Importablauf umgesetzt. Zuordnung zu den 47 Punkten:

| Punkte | Umsetzung |
| --- | --- |
| 1–7 | Gemeinsame Qualitätsprüfung gegen leere und generische Werte in Backend und Frontend; keine Übernahme von „Ohne Betreff“. Feldrevisionen schützen manuelle Eingaben und bewusstes Leeren, auch während laufender Anfragen. KI-Chips kennzeichnen die Herkunft direkt am Feld. Der Zusatzbereich unter dem Formular mit Änderungsvorschlägen und Zurücksetzen wurde entfernt. |
| 8–10 und Formulartabelle | Import und Dokumentendetailschublade verwenden `DocumentMetadataFields` sowie denselben `TagInlineEditor`. Datum wird beim Verlassen normalisiert, Fehler werden am Feld erklärt. Im Import sind alle Felder außer Notizen Pflichtfelder; die Sternmarkierungen entfallen. KI-Chips stehen rechts über dem jeweiligen Eingabefeld, mit Abstand zur vorherigen Feldgruppe. Verwaltungsbuttons in den Importfeldern wurden entfernt; unbekannte Korrespondenten werden nicht automatisch angelegt. |
| 11–12 | Auswahlimport erstellt einen Auftrag für die gewählten Seiten und entfernt erst nach bestätigtem Erfolg ausschließlich diese Seiten aus dem Entwurf. Nicht gewählte und später eingetroffene Seiten bleiben erhalten. Die Inbox wird nur für vollständig erledigte Quellen bestätigt. |
| 13–16 | Sichtbare Scan-, Abschluss- und Abbruchaktionen; dauerhafte Jobfehler; Import während aktiver Erfassung bzw. Bereinigung gesperrt. Client-Anfragen und Gerätesperre verhindern doppelte Scanaufträge und konkurrierende Bedienung. |
| 17–19 | Konservative Hinweise auf leere, kontrastarme, schiefe oder möglicherweise abgeschnittene Seiten. Seitenänderungen werden direkt übernommen; die Quellen bleiben bis zum Import oder ausdrücklichen Verwerfen verfügbar. Drehen, Löschen und Farbmodus sind direkt in der Vorschauleiste erreichbar, auf schmalen Ansichten mit Zeilenumbruch. Die Farbwahl gilt unabhängig von der Auswahl für alle Seiten und wird von später hinzugefügten Quellen übernommen. Livebilder, Miniaturen und der fertige Import berücksichtigen den Modus; Farbmodus-Chips auf Miniaturen entfallen. |
| 20–22 | Die Analyse verwendet die tatsächlichen Seitenreferenzen, ihre Reihenfolge, Drehung und Quellenfassung. Veraltete Antworten werden verworfen; neue Seiten führen zu konsolidierter Analyse. Der zusätzliche Hinweis zum Analyseumfang unter dem Formular wurde entfernt. |
| 23–29 | OCR berücksichtigt Textqualität und erhält Zeilenumbrüche. Der Modellkontext priorisiert Absender, Betreff und relevante Fakten. Datumsangaben brauchen einen Dokumentbeleg. Modellantworten durchlaufen ein typisiertes Schema. Zahlen und Verpflichtungen in Zusammenfassungen werden auf Belege geprüft; ein unbrauchbarer Text fällt auf deterministische Metadaten zurück. Die zusätzlichen Prüfmenüs für Datumsangaben und Fundstellen unter dem Formular wurden entfernt. |
| 30–32 | Die erneute Metadatenanalyse startet über den KI-Button rechts im angehefteten Formularheader und umgeht den Cache. Der Header zeigt den aktuellen Fortschritt; Details sind per Tooltip erreichbar. Das zusätzliche Aktionsmenü wurde entfernt. Cache-Prüfung berücksichtigt Quellenfassung, Konfiguration und Dokumenttypen; jede Antwort erhält eine Ergebnisrevision. Fortschritt hat Vorrang vor bereits gefüllten Feldern. |
| 33–35 | Eine dauerhaft am Dokument gespeicherte Importbestätigung und ein eindeutiger Datenbankindex sichern Wiederholungen ab. PDF, Metadaten, neue Tags und Aufträge werden gemeinsam bestätigt. Teilerfolge werden dokumentweise abgeschlossen. Manuelle Datums-/Tagentscheidungen bleiben auch bei nachgelagerter Verarbeitung geschützt. |
| 36–40 | Formulare, Vorschläge und Fehler gehören zum ausgewählten Dokument. Entwürfe einschließlich offener Aufträge werden im Browser pro Konto gesichert und wiederhergestellt. Dubletten verweisen auf das vorhandene Dokument. Dateien werden unabhängig hochgeladen; ein einzelner Fehler verwirft den übrigen Stapel nicht. Die Ordnerauswahl wurde entfernt. Erfolgstexte berücksichtigen die tatsächlich gestartete Verarbeitung. |
| 41–46 | Einspaltige Seitenliste links, große Seitenvorschau in der Mitte und Formular rechts; nutzbare mobile Anordnung und Tastaturzugang zu Seiten. Die gemeinsame Vorschauleiste blendet sich bei Hover oder Tastaturfokus ein und bleibt bei Touch sichtbar. Die Seitenlistensteuerung sitzt transparent am unteren Rand, das Fenster ist auf 1200 px begrenzt. Analysen und nachgeladene Miniaturen laufen in begrenzten Warteschlangen; Vorschaucaches sind begrenzt. Gemeinsame Feldkomponenten, Formular-, Entwurfs- und Qualitätsmodule entlasten den Dialog. Dokumenttexte und rohe Modellantworten wurden aus den betroffenen Routinelogs entfernt. |
| 47 | Die Farbkonvertierung erhält strukturierte Fehlerursachen und Seitenbezug. Schon passende Bereinigungsfassungen werden wiederverwendet. Graustufen nutzen Ghostscript zum Erhalt von Text und Vektoren; Bildkonvertierung hat ein speicherabhängiges Pixelbudget. Eine begrenzte Wiederholung erhält den Farbmodus, eine reduzierte Auflösung wird gemeldet. Vorschau und Commit verwenden denselben Zusammenstellungsweg einschließlich Beschnitt und Drehung. Bei Fehlschlag bleiben Quellen und Eingaben erhalten. |

Wichtige neue Dateien:

- [Gemeinsamer Metadateneditor](/Users/admin/Documents/paperMind/frontend/src/components/DocumentMetadataFields.vue)
- [Formularzustand pro Dokument](/Users/admin/Documents/paperMind/frontend/src/composables/useImportDocumentForm.js)
- [Wiederherstellung von Entwürfen](/Users/admin/Documents/paperMind/frontend/src/composables/useImportDraftPersistence.js)
- [Importregeln und Revisionen](/Users/admin/Documents/paperMind/frontend/src/utils/importWorkflow.js)
- [Qualitätsprüfung von Metadaten](/Users/admin/Documents/paperMind/backend/app/services/import_analysis_quality.py)
- [Migration für eindeutige Importbestätigungen](/Users/admin/Documents/paperMind/backend/alembic/versions/114_import_receipts.py)
- [Regressionstests des Importablaufs](/Users/admin/Documents/paperMind/backend/tests/test_import_workflow_robustness.py)
- [Datenbanktests für Commit und Wiederholung](/Users/admin/Documents/paperMind/backend/tests/test_import_commit_integration.py)
- [Browserprüfungen des Importdialogs](/Users/admin/Documents/paperMind/frontend/tests/browser/importWorkflow.spec.js)

Die Prüfungen verwenden synthetische PDFs und Browserdaten. Die Migration wurde in der isolierten Testdatenbank ausgeführt. Ein Hardwarelauf am echten Scanner und ein neuer Produktivrollout auf dem Raspberry Pi wurden nicht ausgeführt. Die vorhandene Bridge ist ausschließlich für die in AGENTS.md festgelegten Releases freigegeben.


**Abschließende Validierung des umgesetzten Stands**

- Backend: **674 Tests und 48 Untertests erfolgreich**, keine übersprungenen Tests. Ausgeführt mit `scripts/test_backend.sh` in isolierten Containern und einer eigenen temporären PostgreSQL-Datenbank, einschließlich Migration 114.
- Frontend: **733 Tests erfolgreich** mit `npm test`.
- Browser: **14 Tests erfolgreich** gegen Vite auf `http://127.0.0.1:5179`, einschließlich Seitenauswahl ohne Löschung, Teilerfolg, unveränderter Wiederholung nach verlorener Antwort und Neuladen, Kontotrennung, später KI-Antwort, geänderter Seitenreihenfolge und gezielter Analyse einer ausgewählten Folgeseite.
- Produktionsbuild: erfolgreich, bestehende Größenbudgets eingehalten. Die bekannten Hinweise zu großen optionalen Chunks bleiben bestehen.
- Visuelle Prüfung: Importdialog bei 1440×1000 und 430×900 geprüft. Die mobile Ansicht zeigt eine horizontale Seitenreihe und Formularfelder in voller Breite.
- Zusätzliche Prüfung im lokalen Backend-Container: Graustufen erhalten eine vorhandene Textebene über Ghostscript; realistische mehrseitige A4-Scans behalten Seitengröße und Drehung.
- `git diff --check`: erfolgreich.

Die Auswertung von Scanqualität und Modellbelegen liefert bewusst konservative Prüfhilfen. Nicht lesbare oder defekte Dateien können weiterhin eine nachvollziehbare Fehlermeldung auslösen; der offene Entwurf und die ursprünglichen Quellen bleiben dabei erhalten. Ein Fehler wird nicht durch stillen Wechsel auf einen anderen Farbmodus verdeckt.

**Ergänzung: durchgehende Scanvorschau und Übergang zur ersten Miniatur**

Die Live-URL wird vom Backend nach dem Scannerabschluss entfernt, bevor die Inbox die fertige Quelle liefert. Der Dialog verwirft deshalb das letzte Bild nicht mehr zusammen mit dieser URL. Er hält eine bereits geladene und dekodierte Kopie ausschließlich im Arbeitsspeicher; Fortschritt und Abschlusszustand bleiben während der Vorbereitung sichtbar. Auch ein bereits unterwegs befindlicher letzter Frame darf noch eintreffen. Unvollständige Bilder ersetzen den letzten gültigen Frame nicht.

Beim Öffnen des Hauptbereichs bewegt sich dieses Blatt über 600 ms von seiner bisherigen Position zur ersten Scanminiatur. Das Ziel wird während der Größenänderung des Dialogs laufend gemessen. Die eigentliche Miniatur wird erst nach dem Landen weich eingeblendet. Bei langsamen oder fehlgeschlagenen Miniatur-Anfragen bleibt der Scan als Ersatzvorschau an der Seite sichtbar; eine erfolgreiche Wiederholung löst ihn ab. Parallel hochgeladene PDFs übernehmen kein Scannerbild.

Neue Scans, das Schließen und ein Kontowechsel verwerfen alte Live-Bilder und verspätete Antworten. Nicht mehr benötigte Objekt-URLs werden freigegeben. Nach dem Entfernen importierter Seiten erscheint kein alter Scan erneut im Startbildschirm. Die mobile Seitenreihe und die Einstellungen für reduzierte Bewegung bzw. ausgeschaltete Animationen werden berücksichtigt. Bereits verfügbare Scans warten auch nicht mehr auf die dekorative Einblendanimation des leeren Dialogs.

Die Umsetzung liegt in [useScannerPreviewTransition.js](/Users/admin/Documents/paperMind/frontend/src/composables/useScannerPreviewTransition.js) und dem Importdialog. Die neuen [Browserprüfungen](/Users/admin/Documents/paperMind/frontend/tests/browser/scannerPreviewTransition.spec.js) kontrollieren die durchgehende Sichtbarkeit über einzelne Animationsframes, die Start- und Zielposition, frühe und verspätete Miniaturen, Ladefehler, veraltete Antworten, Kontotrennung, Speicherfreigabe, mobile Darstellung und reduzierte Bewegung. Zusätzlich wurde ein ungültiger Variablenzugriff bei der Übernahme einer schnellen Remote-Vorschau entfernt, damit echte Scannerquellen diesen Pfad zuverlässig durchlaufen.

Erneute lokale Validierung: 733 Frontendtests erfolgreich; die bisherigen 14 Browserprüfungen sowie 14 zusätzliche Prüfungen für die Scanvorschau erfolgreich gegen Vite auf `http://127.0.0.1:5179`; Produktionsbuild und Größenbudgets erfolgreich. Startzustand, Übergang und fertige Miniatur wurden auch visuell geprüft. Ein Lauf am echten Scanner und ein Produktivrollout gehören nicht zu dieser lokalen Prüfung.

Der anschließend ausdrücklich beauftragte Produktivrollout von Commit `8d87348` ist erfolgreich abgeschlossen. Ablauf, verifizierte Sicherung, kontrollierter Rückfall des ersten Prüflaufs und erfolgreiche Abschlussprüfung sind im [Rollout-Protokoll](import-rollout-2026-10-19.md) dokumentiert.
