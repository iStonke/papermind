# Handoff: PaperMind – Farbschema „Kontur" (Hell + Dunkel)

## Überblick
Neues Farbschema für die PaperMind-Weboberfläche (Dokumentenverwaltung, deutschsprachig, lokal unter 127.0.0.1). Ersetzt das bisherige blaugraue Schema, das als trüb und kontaktarm empfunden wurde. Türkis bleibt Markenfarbe, wird aber ausschließlich als **Zustandsfarbe** eingesetzt (Auswahl, Primäraktion, Fokus, aktiver Zustand) – nicht mehr als Flächenfarbe.

## Zu den Design-Dateien
Die beigelegten HTML-Dateien (`*.dc.html`) sind **Design-Referenzen**, keine Produktionsbausteine. Sie zeigen Aussehen und Struktur im Zielzustand. Aufgabe ist, dieses Farbschema im bestehenden PaperMind-Frontend (React) über die vorhandenen Theme-/CSS-Variablen umzusetzen – nicht, das HTML zu übernehmen. Layout, Komponentenstruktur und Verhalten der App bleiben unverändert; **es ist ein reines Farb-/Kontrast-Refactoring**.

## Fidelity
**High-fidelity** für Farbe. Alle Farbwerte sind final und in `tokens.css` vollständig aufgeführt. Abstände, Schriftgrößen und Komponentenanordnung in den Mockups sind Nachbauten aus Screenshots und **nicht** normativ – hier gilt der bestehende Code.

## Design-Prinzipien (verbindlich)
1. **Kein Blaugrau als Fläche.** Neutrale Achse ist hue 222 mit sehr niedriger Chroma (0.008–0.030). Flächen wirken dadurch neutral, nicht bläulich.
2. **Türkis nur für Zustände.** Primärbutton, aktiver Navigationseintrag, Auswahl, Fokusring, aktive Toggles. Keine türkis eingefärbten Karten, Kacheln, Header oder Zähler.
3. **Zonentrennung über Fläche, nicht über Farbe.** Hellmodus: dunkle Tinten-Seitenleiste, weißer Inhalt, leicht getönter Leserbereich. Dunkelmodus: vier klar gestufte Helligkeitsebenen (Seitenleiste am tiefsten → Liste → Karten am hellsten, Leser bewusst zurückgesetzt).
4. **Ein Chip-Ton für alle.** Tags und Dokumenttypen bekommen einen einzigen ruhigen Chip-Ton (`--pm-chip-bg` / `--pm-chip-text`) statt automatisch generierter bunter Farben. In der dunklen Seitenleiste gilt die Sidebar-Variante der Chip-Tokens.
5. **Text steht auf klarem Kontrast.** Fließtext `--pm-text`, Sekundärtext `--pm-text-muted`. Keine weiteren Grautöne dazwischen erfinden.

## Tokens
Vollständig in `tokens.css` (Custom Properties, Hell im `:root`, Dunkel unter `:root[data-theme="dark"]` bzw. `.dark`). Kernwerte:

| Token | Hell | Dunkel |
| --- | --- | --- |
| `--pm-bg` | `#ffffff` | `oklch(0.275 0.014 222)` |
| `--pm-surface-list` | `#ffffff` | `oklch(0.305 0.013 222)` |
| `--pm-surface-card` | `#ffffff` | `oklch(0.345 0.012 222)` |
| `--pm-surface-reader` | `oklch(0.968 0.006 210)` | `oklch(0.250 0.014 222)` |
| `--pm-sidebar-bg` | `oklch(0.272 0.030 222)` | `oklch(0.245 0.016 222)` |
| `--pm-border` | `oklch(0.900 0.008 210)` | `oklch(0.395 0.014 222)` |
| `--pm-text` | `oklch(0.200 0.015 220)` | `oklch(0.965 0.005 220)` |
| `--pm-text-muted` | `oklch(0.475 0.015 220)` | `oklch(0.760 0.014 220)` |
| `--pm-accent` | `oklch(0.475 0.095 205)` | `oklch(0.760 0.105 200)` |
| `--pm-on-accent` | `#ffffff` | `oklch(0.200 0.030 200)` |
| `--pm-selected` | `oklch(0.948 0.026 205)` | `oklch(0.375 0.050 205)` |
| `--pm-chip-bg` | `oklch(0.945 0.008 210)` | `oklch(0.395 0.014 222)` |

Wichtig für den Dunkelmodus: `--pm-on-accent` ist **dunkel**, weil der Akzent dort hell ist. Primärbuttons im Dunkelmodus also dunkle Schrift auf hellem Türkis.

## Screens im Bundle
1. **Dokumentliste + Leser** (`PMScreen.dc.html`) – Seitenleiste (Suche, Bibliothek-Navigation, Tags, Dokumenttypen, Nutzerfuß), Dokumentliste mit Kopf/Filterzeile/Zeilen, Leserbereich mit schwebender Dokumentkarte.
2. **Einstellungen → Darstellung** (`PMSettings.dc.html`) – Dialog mit linker Rubrikenleiste, Farbvariation-Swatches, Thema-Segmented-Control, Auswahlfeld, Toggles.
3. **Vergleichsdokument** (`PaperMind Farbschema.dc.html`) – alle Varianten und die Tokenübersicht; Runde 3 oben ist die finale Festlegung (Hell = 1c, Dunkel = 2a).

## Umsetzungshinweise
- Bestehende Theme-Variablen 1:1 auf die Tokens mappen; keine Hex-Werte in Komponenten hart verdrahten.
- Automatische Tag-Farbgenerierung entfernen bzw. hinter einem Flag deaktivieren; Chips laufen über einen Ton.
- Chart-/Statistikfarben im Dashboard (nicht Teil dieser Runde) danach ableiten: eine Farbfamilie aus dem Akzent-Hue, Abstufungen über Lightness.
- Fokusring: 2 px `--pm-accent` außen, `outline-offset: 2px`.
- Kontrast wurde optisch, nicht formal nach WCAG geprüft.

## Dateien
- `tokens.css` – vollständige Token-Definition
- `PMScreen.dc.html`, `PMSettings.dc.html` – Referenzscreens
- `PaperMind Farbschema.dc.html` – Vergleichs-/Entscheidungsdokument
- `CLAUDE_CODE_PROMPT.md` – fertiger Prompt für Claude Code
