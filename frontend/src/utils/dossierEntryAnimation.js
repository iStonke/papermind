let pendingSidebarEntry = false;

export function requestDossierSidebarEntryAnimation() {
  pendingSidebarEntry = true;
}

export function consumeDossierSidebarEntryAnimation() {
  if (!pendingSidebarEntry) return false;
  pendingSidebarEntry = false;
  return true;
}
