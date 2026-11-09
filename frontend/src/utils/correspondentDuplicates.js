import { findCorrespondentSuggestions } from './correspondentSuggestions.js';

/** Zusammenführen geht nur bei gleichem Typ – Einträge ohne Typ passen zu allen. */
export function canMergeCorrespondents(a, b) {
  return Boolean(a && b) && a.id !== b.id && (!a.kind || !b.kind || a.kind === b.kind);
}

const REASONS = {
  alias: 'Gleicher Name als Alias',
  legalForm: 'Nur die Rechtsform unterscheidet sich',
  spelling: 'Gleiche Schreibweise bis auf Leer- und Bindestriche',
};

/**
 * Wahrscheinliche Doppel eines Korrespondenten: gleicher Name als Alias, nur
 * andere Rechtsform oder nur andere Leer-/Bindestriche. Bloße Teiltreffer
 * („Vodafone“ in „Vodafone Kabel“) zählen bewusst nicht.
 */
export function findDuplicateCandidates(items, correspondent) {
  if (!correspondent) return [];
  const others = items.filter(item => canMergeCorrespondents(item, correspondent));
  const names = [correspondent.name, ...(correspondent.aliases || []).map(alias => alias.alias)];
  const best = new Map();
  for (const name of names) {
    for (const match of findCorrespondentSuggestions(others, name)) {
      if (match.score < 2) continue;
      const reason = match.exact ? 'alias' : match.legalFormOnly ? 'legalForm' : 'spelling';
      const current = best.get(match.correspondent.id);
      if (!current || match.score > current.score) {
        best.set(match.correspondent.id, { correspondent: match.correspondent, score: match.score, reason, label: REASONS[reason] });
      }
    }
  }
  return [...best.values()].sort((a, b) => b.score - a.score
    || Number(b.correspondent.usage_count || 0) - Number(a.correspondent.usage_count || 0)
    || a.correspondent.name.localeCompare(b.correspondent.name, 'de-DE'));
}

/** Wer bleibt, wenn nichts anderes gewählt ist: der Eintrag mit mehr Dokumenten, bei Gleichstand der aktuelle. */
export function preferredMergeTarget(current, other) {
  return Number(other?.usage_count || 0) > Number(current?.usage_count || 0) ? other : current;
}

/** Schlüssel eines Paars, unabhängig von der Reihenfolge („idA|idB“). */
export function duplicatePairKey(a, b) {
  return [String(a), String(b)].sort().join('|');
}

/**
 * Alle wahrscheinlichen Doppel als Paare, jedes nur einmal und alphabetisch
 * geordnet; als „Kein Doppel“ markierte Paare (dismissed) entfallen.
 */
export function findDuplicatePairs(items = [], dismissed = []) {
  const hidden = new Set(dismissed);
  const byName = (a, b) => a.name.localeCompare(b.name, 'de-DE');
  const seen = new Set();
  const pairs = [];
  for (const item of items) {
    for (const match of findDuplicateCandidates(items, item)) {
      const key = duplicatePairKey(item.id, match.correspondent.id);
      if (seen.has(key) || hidden.has(key)) continue;
      seen.add(key);
      const [a, b] = [item, match.correspondent].sort(byName);
      pairs.push({ key, a, b, reason: match.reason, label: match.label });
    }
  }
  return pairs.sort((x, y) => byName(x.a, y.a) || byName(x.b, y.b));
}
