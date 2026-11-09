import { splitLegalForm } from './legalForms.js';

/**
 * Aufräum-Vorschläge für die Korrespondenten-Übersicht (Doppelte haben eine
 * eigene Kachel, siehe findDuplicatePairs):
 * - shortNames: Einträge mit Rechtsform, aber ohne Kurznamen → Name ohne Rechtsform.
 * - empties: keine Dokumente und niemand zugeordnet (gefahrlos löschbar).
 */
export function findCleanupSuggestions(items = [], membersOf = () => []) {
  const byName = (a, b) => a.name.localeCompare(b.name, 'de-DE');
  const shortNames = items
    .filter(item => item.kind !== 'collection' && !String(item.short_name || '').trim())
    .map(item => ({ item, split: splitLegalForm(item.name) }))
    .filter(({ split }) => split.legalForm)
    .map(({ item, split }) => ({ id: item.id, name: item.name, suggestion: split.base.slice(0, 60).trimEnd() }))
    .sort(byName);
  // Nur mit bekannter Zählung: fehlt usage_count, ist der Eintrag nicht sicher leer.
  const empties = items
    .filter(item => item.usage_count != null && Number(item.usage_count) === 0 && !membersOf(item.id).length)
    .sort(byName);
  return { shortNames, empties };
}

export function cleanupSuggestionCount({ shortNames, empties }) {
  return shortNames.length + empties.length;
}
