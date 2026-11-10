/**
 * Vorschlag für die Zuordnung eines offenen Dokuments (Karte und Sammelaktion
 * „Alle Vorschläge übernehmen“ nutzen dieselbe Regel):
 *  1. im Sammlungsmodus das im Dokument genannte Mitglied,
 *  2. sonst ein bestehender Korrespondent, dessen Name oder Alias dem
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
  const sender = normalizedSender(item);
  const key = senderKey(sender);
  if (!key) return null;
  const exactMatch = store.findByName(sender);
  if (exactMatch) return exactMatch;
  const matches = (store.correspondents || []).filter(correspondent =>
    [correspondent.name, ...(correspondent.aliases || []).map(alias => alias.alias)].some(name => senderKey(name) === key));
  return matches.length === 1 ? matches[0] : null;
}
