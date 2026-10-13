const collator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });
const CORRESPONDENT_TYPES = {
  organization: { label: 'Organisation', icon: 'mdi-domain' },
  person: { label: 'Person', icon: 'mdi-account-outline' },
  collection: { label: 'Sammlung', icon: 'mdi-shape-outline' },
};

export function prepareCorrespondentGroups(groups) {
  return (Array.isArray(groups) ? groups : []).map(group => ({
    ...group,
    key: group.correspondent_id || 'unassigned',
    unassigned: !group.correspondent_id,
    label: String(group.short_name || group.name || '').trim()
      || (group.correspondent_id ? 'Unbenannter Korrespondent' : 'Ohne Korrespondent'),
    kindLabel: group.correspondent_id ? CORRESPONDENT_TYPES[group.kind]?.label || '' : '',
    kindIcon: group.correspondent_id ? CORRESPONDENT_TYPES[group.kind]?.icon || '' : '',
  })).sort((left, right) => {
    if (!left.correspondent_id) return right.correspondent_id ? 1 : 0;
    if (!right.correspondent_id) return -1;
    return collator.compare(left.label, right.label) || collator.compare(left.key, right.key);
  });
}

export function correspondentInitials(name) {
  const value = String(name || '').trim();
  if (/^[\p{Lu}\d]{2,4}$/u.test(value)) return value;
  const words = value.split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words.at(-1)[0] : value.slice(0, 2)).toLocaleUpperCase('de-DE');
}

export function visibleDocumentTags(document) {
  return [...(Array.isArray(document.tags) ? document.tags : [])]
    .sort((left, right) => collator.compare(left.name || '', right.name || '')
      || collator.compare(left.id || '', right.id || ''))
    .slice(0, 2);
}

export function correspondentRequestPath(queryPath, { group, offset = 0 } = {}) {
  const [path, query = ''] = queryPath.split('?');
  const params = new URLSearchParams(query);
  params.set('offset', String(offset));
  params.set('limit', group ? '50' : '1');
  params.set('include_total', 'false');
  if (!group) {
    params.set('include_correspondent_groups', 'true');
  } else {
    params.delete('include_correspondent_groups');
    if (group.correspondent_id) params.set('correspondent_id', group.correspondent_id);
    else params.set('without_correspondent', 'true');
    params.set('sort', path.startsWith('/api/smart-folders/') ? 'doc_date_desc' : 'correspondent_date');
    params.set('order', 'desc');
  }
  return `${path}?${params}`;
}
