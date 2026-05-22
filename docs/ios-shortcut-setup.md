# iOS Shortcut — PaperMind One-Click-Scan

Mit diesem Shortcut scannst du ein Dokument auf dem iPhone und es landet automatisch in PaperMind — ein Tipp, fertig.

---

## Voraussetzungen

- Raspberry Pi läuft, PaperMind ist erreichbar (z.B. `http://192.168.1.42:8040`)
- `DIRECT_UPLOAD_API_KEY` ist in der `.env` gesetzt und der Pi neu gestartet
- iOS 16 oder neuer

---

## Einrichtung: Schritt für Schritt

### 1. API-Key generieren und eintragen

Auf dem Pi (einmalig):

```bash
openssl rand -hex 32
```

Den ausgegebenen Wert in die `.env` des Projekts eintragen:

```
DIRECT_UPLOAD_API_KEY=<dein_generierter_key>
```

Danach Backend neu starten:

```bash
docker compose up -d --build backend
```

---

### 2. Shortcut erstellen

Öffne die **Shortcuts**-App auf dem iPhone und tippe auf **+** (neuer Shortcut).

Füge diese Aktionen in der Reihenfolge hinzu:

#### Aktion 1: Dokument scannen
- Suche nach **„Dokument scannen"** (Kategorie: Dokumente)
- Einstellung: **Mehrere Seiten erlauben** → Ein

#### Aktion 2: PDF erstellen
- Suche nach **„PDF erstellen"**
- Eingabe: Ergebnis von Schritt 1 (wird automatisch verknüpft)

#### Aktion 3: URL-Inhalt abrufen (= HTTP POST)
- Suche nach **„URL-Inhalt abrufen"**
- **URL:** `http://<PI_IP>:8040/api/direct-upload`
  *(ersetze `<PI_IP>` durch die IP-Adresse deines Pi, z.B. `192.168.1.42`)*
- **Methode:** POST
- **Headers** → Kopfzeile hinzufügen:
  - Name: `Authorization`
  - Wert: `Bearer <DEIN_API_KEY>`
- **Anforderungstext:** Formular
  - Feld hinzufügen → Typ: **Datei**
  - Name: `files`
  - Wert: Ergebnis von Aktion 2 (das PDF)

#### Aktion 4 (optional): Mitteilung anzeigen
- Suche nach **„Mitteilung anzeigen"**
- Text: `Scan hochgeladen ✓`

---

### 3. Shortcut benennen und auf Homescreen legen

- Tippe oben auf den Shortcut-Namen → z.B. **„Scan → PaperMind"**
- Tippe auf das Icon für ein eigenes Symbol/Farbe
- Tippe auf **Zum Home-Bildschirm hinzufügen**

---

## Verwendung

1. Shortcut antippen
2. Kamera zeigt sich — Dokument scannen (mehrere Seiten möglich)
3. **Senden** tippen
4. Fertig. Das Dokument erscheint in PaperMind und OCR startet automatisch.

---

## Fehlersuche

| Problem | Ursache | Lösung |
|---|---|---|
| „Verbindung abgelehnt" | Pi-IP falsch oder Pi nicht erreichbar | IP in Shortcut prüfen, Pi anpingen |
| HTTP 403 | Falscher API-Key | Key in `.env` und Shortcut vergleichen |
| HTTP 503 | `DIRECT_UPLOAD_API_KEY` nicht in `.env` gesetzt | `.env` prüfen, Backend neu starten |
| HTTP 400 | Datei fehlt oder kein PDF | Aktion 2 „PDF erstellen" prüfen |

### Verbindung testen (curl vom Mac)

```bash
curl -v \
  -H "Authorization: Bearer <DEIN_API_KEY>" \
  -F "files=@/pfad/zu/test.pdf" \
  http://<PI_IP>:8040/api/direct-upload
```

Erwartete Antwort (HTTP 201):
```json
{
  "uploaded": 1,
  "committed": 1,
  "errors": 0,
  "documents": [{"doc_id": "...", "title": "test", "page_count": 2}],
  "error_details": []
}
```

---

## Sicherheitshinweis

Der API-Key ist ein einfaches geteiltes Geheimnis — ausreichend für den Heimnetz-Betrieb. Setze die App nie ohne VPN oder Reverse-Proxy mit HTTPS ins öffentliche Internet.
