import { correspondentDisplayName, correspondentParentName } from '../../utils/correspondentHierarchy.js';

export function resolveDocumentCorrespondent(document, findCorrespondentById = () => null, { showParent = true } = {}) {
  const embedded = document?.correspondent;
  const correspondentId = String(document?.correspondent_id || '').trim();
  const canonical = correspondentId ? findCorrespondentById(correspondentId) : null;

  const name = correspondentDisplayName({
    name: document?.correspondent_name || embedded?.name || embedded?.title || canonical?.name,
    short_name: canonical?.short_name !== undefined
      ? canonical.short_name
      : document?.correspondent_short_name ?? embedded?.short_name,
    kind: canonical?.kind ?? document?.correspondent_kind ?? embedded?.kind,
  });
  const organization = showParent ? correspondentParentName(canonical ?? embedded, findCorrespondentById) : '';
  return organization && name ? `${organization} · ${name}` : name;
}
