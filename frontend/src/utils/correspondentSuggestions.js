import { namesEquivalent, stripLegalForm } from './legalForms.js';

// Exact identity remains distinct from similarity: punctuation is only a suggestion.
export function correspondentNameKey(value) {
  return String(value || '').normalize('NFC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase('de-DE');
}
// Similarity ignores spaces, hyphens and a trailing legal form („GmbH", „e.V." …).
function compact(value) {
  return correspondentNameKey(stripLegalForm(value)).replace(/[\s\p{Pd}]+/gu, '');
}
// score: 3 exact · 2.5 same name, only the legal form differs · 2 same letters · 1 contains
export function findCorrespondentSuggestions(items, name) {
  const key = correspondentNameKey(name);
  if (key.length < 2) return [];
  const needle = compact(name);
  return items.flatMap(correspondent => {
    const names = [correspondent.name, ...(correspondent.aliases || []).map(a => a.alias)];
    const exact = names.some(value => correspondentNameKey(value) === key);
    const legalFormName = exact ? null : names.find(value => namesEquivalent(value, name));
    const matchingName = legalFormName || names.find(value => compact(value) === needle)
      || (needle.length >= 4 ? names.find(value => {
        const candidate = compact(value);
        return candidate.includes(needle) || (candidate.length >= 4 && needle.includes(candidate));
      }) : null);
    if (!exact && !matchingName) return [];
    const score = exact ? 3 : legalFormName ? 2.5 : compact(matchingName) === needle ? 2 : 1;
    return [{ correspondent, exact, legalFormOnly: Boolean(legalFormName), matchedName: matchingName || correspondent.name, score }];
  }).sort((a, b) => b.score - a.score || a.correspondent.name.localeCompare(b.correspondent.name, 'de-DE'));
}
