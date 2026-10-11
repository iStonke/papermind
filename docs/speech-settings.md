# Sprachausgabe für Notizen

Alle persönlichen Vorgaben liegen unter **Einstellungen → Notizen →
Sprachausgabe**. Sie werden pro Benutzer gespeichert und gelten sowohl für
markierten Text als auch für den Audioexport. Bestehende Stimmen und
Sprachmodi werden übernommen. Alte Exportaufträge erhalten die bisherigen
Rhythmuswerte, Piper und die neue deutsche Zahlenaussprache.

## Bedienung und Verhalten

- **Sprachmodus:** automatisch, Deutsch oder Englisch. Englische Abschnitte
  verwenden Ryan High (Piper), auch wenn für Deutsch Kokoro oder CosyVoice
  gewählt ist. Die fünf deutschen Stimmvarianten gehören zu Piper.
- **Tempo:** 0,6–1,5×; bei Piper inverse length_scale, bei den Thorsten-Diensten
  der native speed-Parameter. Keine nachträgliche Änderung der WAV-Tonhöhe.
- **Pausen:** Satz 0,05–0,8 s, Absatz 0,1–1,8 s; Absatzpause mindestens Satzpause.
  Standard 1×, 0,18 s und 0,38 s. Überlange Randstille wird mit Schutzabstand
  gekürzt. Sprach- und Exportsegmentgrenzen berücksichtigen dieselben Pausen.
- **Zahlenaussprache:** gültige deutsche Datumsangaben, Uhrzeiten, Zahlen,
  Prozentwerte, Währungen und gängige Einheiten. Zum Beispiel
  „am 11.10.2026“ → „am elften Oktober zweitausendsechsundzwanzig“,
  „14:30 Uhr“ → „vierzehn Uhr dreißig“, „1,50 €“ → „ein Euro und fünfzig Cent“.
  URLs, E-Mail-Adressen, alphanumerische Kennungen, führende Nullen,
  ungültige Datumsangaben und unbeschriftete Versionsnummern bleiben erhalten.
- **Aussprachewörterbuch:** bis zu 100 Einträge, ganze Wörter/Wortgruppen;
  optionale Groß-/Kleinschreibung, Aktivieren, Bearbeiten, Löschen.
  Längere Begriffe zuerst, literaler Abgleich, eine Ersetzungsrunde.
  Gilt vor Zahlen- und Abkürzungsaufbereitung; Originalnotizen bleiben unverändert.
- **Hörprobe/Vergleich:** derselbe Text (maximal 1.200 Zeichen) mit demselben
  Tempo, Pausen und Wörterbuch. Jeder bereitstehende Anbieter hat einen
  Hörknopf. Servermessung zeigt Erzeugungszeit, WAV-Länge, Verhältnis zur
  Echtzeit und tatsächlich verwendete Engine. Unter 1× = schneller als
  Echtzeit. Bei Text-/Einstellungsänderung werden alte Messwerte gelöscht.
  Safari wird durch den direkten Wiedergabestart im Klick vorbereitet.
  Bei einer Wiedergabesperre bleibt die Datei über den Audioplayer startbar.

Ein Exportauftrag speichert einen vollständigen Optionsstand. Änderungen in
den Einstellungen ändern daher keinen bereits gestarteten Auftrag, auch nicht
nach einem Worker-Neustart oder beim Wiederholen dieses Auftrags.

## Optionale lokale Engines

Piper funktioniert mit den vorhandenen Backend-/Worker-Images.
docker-compose.speech.yml ergänzt ausdrücklich aktivierte Profile:
speech-kokoro und speech-cosyvoice. Ein gewöhnliches Update startet diese
Dienste nicht. Beide API-Ziele sind Serverkonfiguration, keine vom Browser
übergebenen URLs; es werden keine Cloud-TTS-Dienste verwendet.

Lokal Kokoro starten (bestehende Dienste bleiben dabei stehen):

    docker compose -f docker-compose.yml -f docker-compose.speech.yml \
      --profile speech-kokoro up -d --no-deps tts-kokoro

Entsprechend für einen ausreichend ausgestatteten Server:

    docker compose -f docker-compose.yml -f docker-compose.speech.yml \
      --profile speech-cosyvoice up -d --no-deps tts-cosyvoice

Für Produktion ersetzt der Betreiber die Basisdatei durch
docker-compose.prod.yml. **Agenten nutzen am Produktiv-Pi weiterhin nur die
freigegebene feste Bridge-Aktion; diese Anleitung erteilt keine neue Freigabe.**
Ein Rollout muss Frontend, Backend und Worker gemeinsam aktualisieren;
num2words gehört in beide Python-Images. Keine Datenbankmigration erforderlich.

Standardziele im Compose-Netzwerk:

| Variable | Vorgabe |
| --- | --- |
| TTS_KOKORO_URL | http://tts-kokoro:8000 |
| TTS_COSYVOICE_URL | http://tts-cosyvoice:8000 |
| TTS_EXTERNAL_TIMEOUT_SECONDS | 300 (zulässig 5–900) |

Das Overlay reicht diese Variablen an Backend und Worker weiter. Für andere
lokale Server die Werte in der Serverumgebung setzen und beide Dienste mit dem
Overlay aktualisieren. Kein Überschreiben nötig für die mitgelieferten Dienste.
Hostports 8055/8056 sind ausschließlich an 127.0.0.1 gebunden. Modellspeicher
liegt in separaten persistenten Volumes. Kokoro ist per Image-Digest und
Checkpoint 5 fixiert; CosyVoice verwendet das offizielle cosyvoice3-Image.
Das Overlay begrenzt CPU/RAM. Bei Speicherfehlern die Begrenzung auf der
Zielhardware prüfen; CosyVoice ist kein automatisch aktivierter Pi-Standard.

Offizielle Schnittstellen:
[Kokoro](https://thorsten-voice.de/en/guides/kokoro/) verwendet JSON
POST /tts mit text/speed; [CosyVoice](https://thorsten-voice.de/en/guides/cosyvoice/)
Formfelder. Beide liefern WAV und haben GET /health. Kokoro unterstützt
amd64/arm64 auf CPU. CosyVoice lädt beim ersten Start rund 8,5 GB Modelle
und ist ohne NVIDIA-GPU deutlich langsamer. Der Einstellungsbereich sperrt
Hörproben für Dienste, die noch nicht bereit sind, statt Messwerte zu erfinden.

## Tatsächlich durchgeführter lokaler Vergleich

11. Oktober 2026, Docker auf dem lokalen Mac, Kokoro auf 2 CPUs begrenzt.
Identischer deutscher Text (167 Zeichen vor Aufbereitung), Tempo 1×,
Satzpause 0,18 s, Absatzpause 0,38 s, Zahlenaussprache aktiv.
Jeweils zwei Durchläufe; Synthese ist nicht deterministisch, daher leicht
unterschiedliche Audiolängen.

| Engine / Durchlauf | Erzeugung | Audiolänge | Verhältnis zur Echtzeit |
| --- | ---: | ---: | ---: |
| Piper / 1 | 4,030 s | 13,767 s | 0,293× |
| Piper / 2 | 2,346 s | 13,212 s | 0,178× |
| Kokoro / 1 | 9,097 s | 13,000 s | 0,700× |
| Kokoro / 2 | 7,598 s | 13,010 s | 0,584× |

Audiodateien und Rohmesswerte liegen lokal in .runtime/speech-settings/.
Dies sind **keine Pi-Messungen und keine Bewertung des natürlichen Klangs**.
Der Hörvergleich entscheidet über die subjektive Qualität. CosyVoice wurde
hier nicht gestartet; sein HTTP-/WAV-Vertrag ist getestet und seine
Nichtverfügbarkeit wird angezeigt. Für den Pi zuerst Kokoro messen und hören;
Piper bleibt voreingestellt.
