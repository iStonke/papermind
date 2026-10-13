const collator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });

export function documentTypeGroupKey(name) {
  const normalized = String(name || '').trim().toLowerCase();
  return normalized ? `type:${encodeURIComponent(normalized)}` : 'unassigned';
}

export function prepareDocumentTypeGroups(groups) {
  return (Array.isArray(groups) ? groups : []).map(group => ({
    ...group,
    key: documentTypeGroupKey(group.document_type),
    name: String(group.document_type || '').trim(),
    label: String(group.document_type || '').trim() || 'Ohne Dokumenttyp',
    unassigned: !String(group.document_type || '').trim(),
  })).sort((left, right) => {
    if (left.unassigned) return right.unassigned ? 0 : 1;
    if (right.unassigned) return -1;
    return collator.compare(left.label, right.label) || collator.compare(left.key, right.key);
  });
}

export function documentTypeRequestPath(queryPath, { group, offset = 0 } = {}) {
  const [path, query = ''] = queryPath.split('?');
  const params = new URLSearchParams(query);
  params.set('offset', String(offset));
  params.set('limit', group ? '50' : '1');
  params.set('include_total', 'false');
  params.delete('include_correspondent_groups');
  if (!group) {
    params.set('include_document_type_groups', 'true');
  } else {
    params.delete('include_document_type_groups');
    if (group.document_type) params.set('document_type', group.document_type);
    else params.set('without_document_type', 'true');
    params.set('sort', path.startsWith('/api/smart-folders/') ? 'doc_date_desc' : 'correspondent_date');
    params.set('order', 'desc');
  }
  return `${path}?${params}`;
}
