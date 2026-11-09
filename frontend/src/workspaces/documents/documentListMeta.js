export function resolveDocumentCorrespondent(document, findCorrespondentById = () => null, { preferShort = true, showParent = true } = {}) {
  const embedded = document?.correspondent;
  const correspondentId = String(document?.correspondent_id || '').trim();
  const canonical = correspondentId ? findCorrespondentById(correspondentId) : null;

  const name = String(
    (preferShort && (document?.correspondent_short_name || embedded?.short_name || canonical?.short_name)) ||
    document?.correspondent_name ||
    embedded?.name ||
    embedded?.title ||
    canonical?.name ||
    ''
  ).trim();
  // Personen mit Organisation: „Organisation · Person“ (gemeinsame Schreibweise).
  const parent = canonical?.parent_id ? findCorrespondentById(canonical.parent_id) : null;
  const organization = showParent ? String((preferShort && parent?.short_name) || parent?.name || canonical?.parent_name || '').trim() : '';
  return organization && name ? `${organization} · ${name}` : name;
}
