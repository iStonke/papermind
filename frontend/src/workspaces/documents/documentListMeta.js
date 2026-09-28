export function resolveDocumentCorrespondent(document, findCorrespondentById = () => null) {
  const embedded = document?.correspondent;
  const correspondentId = String(document?.correspondent_id || '').trim();
  const canonical = correspondentId ? findCorrespondentById(correspondentId) : null;

  return String(
    document?.correspondent_short_name ||
    embedded?.short_name ||
    canonical?.short_name ||
    document?.correspondent_name ||
    embedded?.name ||
    embedded?.title ||
    canonical?.name ||
    ''
  ).trim();
}
