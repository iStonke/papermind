export const DEFAULT_DOSSIER_TITLE = 'Neuer Leuchttisch';

export function shouldDiscardDossierDraft(_dossier, items = []) {
  const hasContents = Array.isArray(items) && items.length > 0;
  return !hasContents;
}
