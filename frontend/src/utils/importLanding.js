import { nextTick } from 'vue';

export async function resolveImportDestination({ documentId, documentsReady, preparedPanel, getPanel, getSidebarTarget }) {
  await documentsReady;
  await nextTick();
  const panel = getPanel();
  if (preparedPanel !== panel) preparedPanel?.cancelImportLanding?.();
  let target = null;
  if (documentId && panel?.beginImportLanding) {
    if (preparedPanel !== panel) panel.prepareImportLanding?.(documentId);
    try { target = await panel.beginImportLanding(documentId); } catch { target = null; }
    if (panel !== getPanel()) target = null;
    if (!target) panel.cancelImportLanding?.();
  }
  return target
    ? { target, panel, destination: 'list' }
    : { target: getSidebarTarget(), panel: null, destination: 'all-documents' };
}

export async function importLayoutReady() {
  await nextTick();
  await new Promise(resolve => requestAnimationFrame(resolve));
}

export function findImportRow(root, documentId) {
  if (!documentId) return null;
  return Array.from(root?.querySelectorAll('[data-document-id]') || [])
    .find(row => row.dataset.documentId === String(documentId)) || null;
}

export function revealImportRow(row, scroller) {
  if (!row || !scroller) return;
  const rect = row.getBoundingClientRect();
  const viewport = scroller.getBoundingClientRect();
  // Ein vorhandenes Item bleibt an seiner sortierten Position. Nur bei Bedarf
  // wird diese Position in den sichtbaren Ausschnitt gescrollt.
  if (rect.top < viewport.top + 40 || rect.bottom > viewport.bottom) {
    scroller.scrollTop += rect.top - viewport.top - (scroller.clientHeight - rect.height) / 2;
  }
}

export function importThumbnailTarget(row, thumbnailSelector, scroller) {
  const thumbnail = row?.querySelector(thumbnailSelector);
  if (!thumbnail?.isConnected || !scroller?.isConnected) return null;
  if (thumbnail.checkVisibility && !thumbnail.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return null;
  const rect = thumbnail.getBoundingClientRect();
  const viewport = scroller.getBoundingClientRect();
  if (rect.width < 4 || rect.height < 4 || rect.top < Math.max(0, viewport.top)
    || rect.bottom > Math.min(window.innerHeight, viewport.bottom)
    || rect.left < Math.max(0, viewport.left) || rect.right > Math.min(window.innerWidth, viewport.right)) return null;
  const style = getComputedStyle(thumbnail);
  return {
    left: rect.left, top: rect.top, width: rect.width, height: rect.height,
    onRealRow: true,
    borderRadius: Number.parseFloat(style.borderTopLeftRadius) || 0,
    borderWidth: Number.parseFloat(style.borderTopWidth) || 0,
    borderColor: style.borderTopColor, backgroundColor: style.backgroundColor,
    boxShadow: style.boxShadow,
  };
}

export async function waitForImportTarget(measure, timeoutMs = 700) {
  const deadline = performance.now() + timeoutMs;
  do {
    await importLayoutReady();
    const target = measure();
    if (target) return target;
  } while (performance.now() < deadline);
  return null;
}
