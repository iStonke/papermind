const normalize = (value) => (value || '').trim().replace(/\s+/gu, ' ');

export function personNameParts(record) {
  if (record.first_name != null || record.last_name != null) {
    return { firstName: record.first_name || '', lastName: record.last_name || '' };
  }
  // Nur als Vorschlag für die Bearbeitung bestehender Namen.
  const [firstName, ...rest] = normalize(record.name).split(' ');
  return { firstName, lastName: rest.join(' ') };
}

export function personNamePayload({ firstName, lastName }) {
  const first_name = normalize(firstName) || null;
  const last_name = normalize(lastName) || null;
  return { name: [first_name, last_name].filter(Boolean).join(' '), first_name, last_name };
}

export function validCorrespondentName(name) {
  const length = normalize(name).length;
  return length >= 2 && length <= 120;
}
