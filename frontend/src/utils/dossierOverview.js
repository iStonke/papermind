export const DOSSIER_OVERVIEW_SORTS = Object.freeze([
  { value: 'updated_desc', label: 'Zuletzt geändert' },
  { value: 'title_asc', label: 'Titel A–Z' },
  { value: 'items_desc', label: 'Meiste Elemente' },
  { value: 'favorites_first', label: 'Favoriten zuerst' },
]);

function normalizedText(value) {
  return String(value || '').toLocaleLowerCase('de-DE');
}

function propertyText(property) {
  if (property?.value_type === 'date') return property.value_date || '';
  if (property?.value_type === 'number') return property.value_number ?? '';
  if (property?.value_type === 'boolean') return property.value_boolean ? 'ja' : 'nein';
  return property?.value_text || '';
}

export function dossierMatchesOverview(entry, { state = 'all', query = '' } = {}) {
  const archived = Boolean(entry?.archived_at);
  if (state === 'archived') {
    if (!archived) return false;
  } else if (archived) {
    return false;
  }

  const needle = normalizedText(query).trim();
  if (!needle) return true;

  const properties = (entry?.properties || [])
    .map((property) => `${property.label || ''} ${propertyText(property)}`)
    .join(' ');
  return normalizedText([
    entry?.title,
    entry?.dossier_type,
    entry?.reference,
    entry?.description,
    entry?.top_note,
    properties,
  ].join(' ')).includes(needle);
}

function dateValue(value) {
  const parsed = Date.parse(value || '');
  return Number.isFinite(parsed) ? parsed : 0;
}

function titleCompare(left, right) {
  return String(left?.title || '').localeCompare(String(right?.title || ''), 'de-DE', {
    sensitivity: 'base',
    numeric: true,
  });
}

export function compareDossiers(left, right, sort = 'updated_desc') {
  if (sort === 'title_asc') return titleCompare(left, right);
  if (sort === 'items_desc') {
    return Number(right?.item_count || 0) - Number(left?.item_count || 0)
      || dateValue(right?.updated_at) - dateValue(left?.updated_at)
      || titleCompare(left, right);
  }
  if (sort === 'favorites_first') {
    return Number(Boolean(right?.is_favorite)) - Number(Boolean(left?.is_favorite))
      || dateValue(right?.updated_at) - dateValue(left?.updated_at)
      || titleCompare(left, right);
  }
  return dateValue(right?.updated_at) - dateValue(left?.updated_at)
    || titleCompare(left, right);
}

export function filterAndSortDossiers(entries, options = {}) {
  return (entries || [])
    .filter((entry) => dossierMatchesOverview(entry, options))
    .sort((left, right) => compareDossiers(left, right, options.sort));
}

export function dossierElementsSummary(entry) {
  const total = Math.max(0, Number(entry?.item_count || 0));
  const documents = Math.max(0, Number(entry?.document_count || 0));
  const other = Math.max(0, total - documents);
  const parts = [];
  if (documents) parts.push(`${documents} PDF`);
  if (other) parts.push(`${other} Notizen/Links`);
  return parts.length ? `${total} · ${parts.join(', ')}` : '0 Elemente';
}
