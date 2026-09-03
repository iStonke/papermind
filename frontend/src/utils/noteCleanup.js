/*
 * „Aufräumen (sinnwahrend)" — Hilfslogik für die KI-gestützte Glättung eines
 * rohen Mitschriebs. Der Editor sammelt die Fließtext-Absätze, nummeriert sie
 * hier als Blöcke ⟦n⟧, schickt sie über denselben Notiz-KI-Stream und ordnet
 * die Antwort blockweise wieder zu. Strukturierte Blöcke (Callouts, Aufgaben,
 * Tabellen …) werden bewusst NICHT übergeben und bleiben unverändert.
 *
 * Diese Datei ist absichtlich frei von TipTap/DOM, damit die riskante String-
 * Logik (Format + Parser) isoliert testbar bleibt.
 */

// Backend begrenzt `selected_text` auf 8000 Zeichen; darunter bleiben, damit die
// Anfrage nicht mit 422 abgelehnt wird. Ist der Mitschrieb länger, wird der
// Nutzer gebeten, einen Abschnitt zu markieren.
export const CLEANUP_INPUT_LIMIT = 7000;

// Seltene Klammer-Marker: praktisch nie Teil eines Mitschriebs, dadurch
// kollisionsarm beim Zurückparsen. Werden vor dem Einfügen restlos entfernt.
export function cleanupMarker(n) {
  return `⟦${n}⟧`;
}

/** Absätze zu einem nummerierten Blocktext bündeln (ein Block = eine Zeile). */
export function formatCleanupInput(texts) {
  return (texts || [])
    .map((text, index) => `${cleanupMarker(index + 1)} ${String(text ?? '').replace(/\s+/g, ' ').trim()}`)
    .join('\n\n');
}

export const CLEANUP_INSTRUCTION = [
  'Du räumst einen rohen, während eines Meetings schnell getippten Mitschrieb auf.',
  'Der AUSGEWÄHLTE TEXT besteht aus nummerierten Blöcken im Format ⟦n⟧.',
  'Formuliere den Inhalt JEDES Blocks in vollständige, gut lesbare Sätze um.',
  '',
  'Strikte Regeln:',
  '- Bewahre Sinn, Aussage und Reihenfolge exakt. Erfinde NICHTS: keine neuen',
  '  Fakten, Namen, Zahlen, Begründungen oder Schlussfolgerungen.',
  '- Verknüpfe Blöcke nicht inhaltlich; jeder Block bleibt für sich.',
  '- Ist ein Fragment wirklich unklar, kennzeichne die Stelle mit [unklar],',
  '  statt zu raten.',
  '- Behalte Fachbegriffe, Eigennamen und Abkürzungen bei.',
  '',
  'Ausgabe: GENAU dieselbe Anzahl Blöcke, in derselben Reihenfolge, jeder Block',
  'eingeleitet mit ⟦n⟧ und danach der ausformulierte Text in EINER Zeile.',
  'Keine Einleitung, keine Aufzählungszeichen, kein Codeblock.',
].join('\n');

/**
 * Zerlegt die Modellantwort sequentiell an den erwarteten Markern ⟦1⟧…⟦N⟧.
 * Nur wenn alle N Marker in Reihenfolge auftauchen und jeder Block Text trägt,
 * gilt das Ergebnis als sicher zuordenbar – sonst wird nichts verändert.
 */
export function parseCleanupOutput(raw, expectedCount) {
  const text = String(raw ?? '');
  const count = Number(expectedCount) || 0;
  if (count < 1) return { ok: false, blocks: [] };

  const blocks = [];
  let cursor = 0;
  for (let i = 1; i <= count; i += 1) {
    const start = text.indexOf(cleanupMarker(i), cursor);
    if (start < 0) return { ok: false, blocks: [] };
    const contentStart = start + cleanupMarker(i).length;
    let contentEnd = text.length;
    if (i < count) {
      const next = text.indexOf(cleanupMarker(i + 1), contentStart);
      if (next < 0) return { ok: false, blocks: [] };
      contentEnd = next;
      cursor = next;
    }
    const block = text.slice(contentStart, contentEnd).replace(/\s+/g, ' ').trim();
    if (!block) return { ok: false, blocks: [] };
    blocks.push(block);
  }
  return { ok: true, blocks };
}

/** Marker für die Live-Vorschau entfernen, Blöcke durch Leerzeilen trennen. */
export function stripCleanupMarks(raw) {
  return String(raw ?? '')
    .replace(/\s*⟦\d+⟧\s*/g, '\n\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
