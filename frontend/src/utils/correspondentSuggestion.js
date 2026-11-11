/**
 * Vorschlag für die Zuordnung eines offenen Dokuments (Karte und Sammelaktion
 * „Alle Vorschläge übernehmen“ nutzen dieselbe Regel) – vorhandene
 * Korrespondenten immer vor einem neu anzulegenden:
 *  1. im Sammlungsmodus das im Dokument genannte Mitglied,
 *  2. der Vorschlag des Backends (`item.suggestion`: Absender, Matcher oder
 *     ein im Dokumenttext eindeutig genannter Korrespondent),
 *  3. sonst ein bestehender Korrespondent, dessen Name oder Alias dem
 *     erkannten Absender entspricht (exakt oder eindeutig bis auf Schreibweise).
 */
import { senderKey } from './senderKey.js';

export function normalizedSender(item) {
  return item?.sender?.trim().replace(/\s+/g, ' ') ?? '';
}

export function suggestCorrespondent(item, store, { mentionedMemberId = null, collectionMode = false } = {}) {
  if (collectionMode && mentionedMemberId) {
    const mentioned = store.findById(mentionedMemberId);
    if (mentioned) return mentioned;
  }
  const fromBackend = item?.suggestion?.correspondent_id ? store.findById(item.suggestion.correspondent_id) : null;
  if (fromBackend) return fromBackend;
  const sender = normalizedSender(item);
  const key = senderKey(sender);
  if (!key) return null;
  const exactMatch = store.findByName(sender);
  if (exactMatch) return exactMatch;
  const matches = (store.correspondents || []).filter(correspondent =>
    [correspondent.name, ...(correspondent.aliases || []).map(alias => alias.alias)].some(name => senderKey(name) === key));
  return matches.length === 1 ? matches[0] : null;
}

/** Grund des Vorschlags für den Tooltip am „Vorschlag“-Chip. */
export function suggestionReason(item, correspondent) {
  if (!correspondent) return '';
  const matchedBy = item?.suggestion?.correspondent_id === correspondent.id ? item.suggestion.matched_by : 'name';
  return {
    text: `${correspondent.name} wird im Dokument genannt`,
    surname: `${correspondent.name} – Name im Dokument genannt`,
    member: `${correspondent.name} wird im Dokument genannt`,
    matcher: `${correspondent.name} – passt zu einer Suchregel`,
  }[matchedBy] || `${correspondent.name} passt zum erkannten Absender`;
}
