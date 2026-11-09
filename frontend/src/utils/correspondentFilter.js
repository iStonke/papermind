import { matchesCorrespondentQuery } from './correspondentHierarchy.js';

/**
 * custom-filter für Vuetify-Auswahlfelder mit Korrespondenten: findet auch über
 * Kurzname und (je nach Einstellung) Aliase. Einträge ohne Korrespondentendaten
 * (z. B. „Neuen Korrespondenten anlegen“) werden über ihren Titel gesucht.
 */
export function createCorrespondentItemFilter(searchAliases = () => true) {
  return (value, query, item) => {
    const raw = item?.raw;
    const title = typeof value === 'string' ? value : item?.title;
    if (raw && typeof raw === 'object' && (raw.name || raw.short_name)) {
      return matchesCorrespondentQuery(raw, query, { aliases: searchAliases(), extra: [title] });
    }
    return matchesCorrespondentQuery(null, query, { extra: [title] });
  };
}
