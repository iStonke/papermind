export function resolveDocumentCorrespondent(document, findCorrespondentById = () => null) {
  const embedded = document?.correspondent;
  const correspondentId = String(document?.correspondent_id || '').trim();
  const canonical = correspondentId ? findCorrespondentById(correspondentId) : null;

  return String(
    document?.correspondent_name ||
    document?.correspondent_short_name ||
    embedded?.short_name ||
    embedded?.name ||
    embedded?.title ||
    canonical?.name ||
    canonical?.short_name ||
    ''
  ).trim();
}
