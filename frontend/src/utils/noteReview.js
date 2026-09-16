/*
 * „KI-Überarbeitung" (Stufe B) — reine, TipTap-/DOM-freie Hilfslogik.
 *
 * Das Modell liefert eine Liste einzelner, überprüfbarer Änderungen als JSON.
 * Diese Datei kümmert sich ausschließlich um das riskante String-Handwerk:
 *  - die Modellantwort robust nach JSON parsen und validieren,
 *  - jede Änderung ehrlich kategorisieren (fix | format | add),
 *  - den wörtlichen `anchor` an der richtigen Fundstelle im Notiztext auflösen
 *    (bei Mehrfachvorkommen über die Reihenfolge der Änderungen).
 *
 * Die Zuordnung von Zeichen-Offsets zu ProseMirror-Positionen und das eigentliche
 * Einfügen liegen bewusst getrennt in `noteReviewDoc.js`, damit diese Logik ohne
 * Editor testbar bleibt.
 */

// Backend begrenzt `note_text` auf 12000 Zeichen; knapp darunter bleiben.
export const NOTE_REVIEW_INPUT_LIMIT = 11000;

export const REVIEW_CATEGORIES = Object.freeze(['fix', 'format', 'add']);
const CONFIDENCE_LEVELS = Object.freeze(['hoch', 'mittel', 'niedrig']);

/** fix/format werden vorausgewählt (opt-out), add muss bestätigt werden (opt-in). */
export function reviewDefaultAccepted(change) {
  return change.cat !== 'add';
}

// Entfernt ausschließlich überzählige Abschlusskommas außerhalb von Strings.
// Anker und Ersatztexte werden dabei niemals umgeschrieben.
function parseJsonCandidate(text) {
  let cleaned = '';
  let quoted = false;
  let escaped = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (!quoted && char === ',' && /^\s*[}\]]/.test(text.slice(i + 1))) continue;
    cleaned += char;
    if (quoted) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') quoted = false;
    } else if (char === '"') quoted = true;
  }
  try { return JSON.parse(cleaned); } catch { return null; }
}

/** Extract only complete, balanced JSON; never complete a truncated response. */
function extractJsonObject(raw) {
  const text = String(raw ?? '').trim();
  const direct = parseJsonCandidate(text);
  if (direct !== null) return direct;
  let start = -1;
  let stack = [];
  let quoted = false;
  let escaped = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (start < 0) {
      if (char !== '{' && char !== '[') continue;
      start = i;
      stack = [char];
      quoted = false;
      escaped = false;
      continue;
    }
    if (quoted) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') quoted = false;
      continue;
    }
    if (char === '"') quoted = true;
    else if (char === '{' || char === '[') stack.push(char);
    else if (char === '}' || char === ']') {
      const expected = char === '}' ? '{' : '[';
      if (stack.pop() !== expected) return null;
      if (!stack.length) {
        const candidate = parseJsonCandidate(text.slice(start, i + 1));
        if (Array.isArray(candidate) || Array.isArray(candidate?.changes)) return candidate;
        start = -1;
      }
    }
  }
  return null;
}

function normalizeChange(entry, fallbackId) {
  if (!entry || typeof entry !== 'object') return null;
  const cat = String(entry.cat ?? '').trim().toLowerCase();
  if (!REVIEW_CATEGORIES.includes(cat)) return null;

  const anchor = typeof entry.anchor === 'string' ? entry.anchor : '';
  if (!anchor.trim()) return null;

  const revised = typeof entry.revised === 'string' ? entry.revised : '';
  // fix/format ohne Ersatztext sind wertlos; add darf leer sein (reiner Hinweis
  // ist trotzdem sinnlos, deshalb auch hier Text verlangen).
  if (!revised.trim()) return null;

  const reason = String(entry.reason ?? '').trim();

  const change = {
    id: Number.isSafeInteger(entry.id) && entry.id > 0 ? entry.id : fallbackId,
    cat,
    anchor,
    revised,
    reason,
    summary: compactReviewSummary(entry.summary, reason, cat),
  };

  if (entry.block_ids !== undefined) {
    if (cat !== 'format' || !Array.isArray(entry.block_ids) || !entry.block_ids.length
      || entry.block_ids.length > 20 || entry.block_ids.some(id => typeof id !== 'string' || !/^b[1-9]\d*$/.test(id))) return null;
    change.blockIds = entry.block_ids;
  }

  if (cat === 'add') {
    const confidence = String(entry.confidence ?? '').trim().toLowerCase();
    // „Ehrliche" Voreinstellung bei fehlender Angabe: niedrig ⇒ bleibt opt-in.
    change.confidence = CONFIDENCE_LEVELS.includes(confidence) ? confidence : 'niedrig';
    change.insertBefore = entry.insert_before === true;
  }

  return change;
}

/**
 * Parst und validiert die komplette Modellantwort.
 * @returns {{ ok: boolean, changes: object[], error: string }}
 */
export function parseReviewOutput(raw) {
  const data = extractJsonObject(raw);
  if (!data || typeof data !== 'object') {
    return { ok: false, changes: [], error: 'Die Antwort war kein gültiges JSON.' };
  }
  const list = Array.isArray(data.changes) ? data.changes : (Array.isArray(data) ? data : null);
  if (!list) {
    return { ok: false, changes: [], error: 'Die Antwort enthielt keine Änderungsliste.' };
  }
  const changes = [];
  const seenIds = new Set();
  list.forEach((entry, index) => {
    const change = normalizeChange(entry, index + 1);
    if (!change) return;
    // Doppelte IDs auf eindeutige laufende Nummern zwingen.
    while (seenIds.has(change.id)) change.id = Number.isSafeInteger(change.id + 1) ? change.id + 1 : 1;
    seenIds.add(change.id);
    changes.push(change);
  });
  if (list.length && !changes.length) {
    return { ok: false, changes: [], error: 'Die Antwort enthielt keine gültigen Vorschläge. Bitte erneut prüfen.' };
  }
  return { ok: true, changes, error: '' };
}

/** Alle Startoffsets von `needle` in `haystack` (ohne Überlappung), aufsteigend. */
function allOccurrences(haystack, needle) {
  const offsets = [];
  if (!needle) return offsets;
  let from = 0;
  for (;;) {
    const at = haystack.indexOf(needle, from);
    if (at < 0) break;
    offsets.push(at);
    from = at + needle.length;
  }
  return offsets;
}

/**
 * Löst für jede Änderung die Zeichen-Fundstelle (`charFrom`/`charTo`) im
 * Notiztext auf. Kommt derselbe anchor mehrfach vor, erhalten die Änderungen
 * die Fundstellen der Reihe nach; gibt es mehr Änderungen als Vorkommen (z. B.
 * eine Korrektur und eine Ergänzung an derselben Stelle), teilen sich die
 * überzähligen die letzte Fundstelle. Nicht auffindbare anchors werden als
 * `found: false` markiert und später ausgeblendet.
 */
export function resolveReviewAnchors(flatText, changes) {
  const text = String(flatText ?? '');
  const consumed = new Map();
  return (changes || []).map((change) => {
    const occurrences = allOccurrences(text, change.anchor);
    if (!occurrences.length) {
      return { ...change, found: false, charFrom: -1, charTo: -1 };
    }
    const used = consumed.get(change.anchor) || 0;
    const index = Math.min(used, occurrences.length - 1);
    consumed.set(change.anchor, used + 1);
    const charFrom = occurrences[index];
    return { ...change, found: true, charFrom, charTo: charFrom + change.anchor.length };
  });
}

/** Zusammenfassung für die Kopfzeile/Übersicht. */
export function summarizeReviewChanges(changes) {
  const auto = changes.filter((c) => c.found && c.cat !== 'add').length;
  const add = changes.filter((c) => c.found && c.cat === 'add').length;
  return { auto, add, total: auto + add };
}

// Alte/abweichende Providerantworten bleiben nutzbar; lange Texte nie in die Karte übernehmen.
export function compactReviewSummary(summary, reason, category) {
  const fallback = { fix: 'Die markierte Textstelle korrigieren.', format: 'Die Darstellung des markierten Abschnitts verbessern.', add: 'Die markierte Stelle ergänzen.' };
  const text = (typeof summary === 'string' && summary.trim() ? summary : reason || fallback[category] || 'Die markierte Stelle überarbeiten.').replace(/\s+/g, ' ').trim();
  return text.length <= 200 ? text : `${text.slice(0, 199).trimEnd()}…`;
}
