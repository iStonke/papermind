import { onBeforeUnmount, ref } from 'vue';
import { findImportRow, importLayoutReady, importThumbnailTarget, revealImportRow, waitForImportTarget } from '../utils/importLanding.js';

export function useDocumentImportLanding({ root, scroller, thumbnailSelector, beforeLocate }) {
  const importLandingThumbDocId = ref('');
  const justArrivedDocId = ref('');
  let revealRequested = false;
  let generation = 0;
  let pulseTimer;
  let thumbnailTimer;

  function cancelImportLanding() {
    generation++;
    clearTimeout(pulseTimer);
    clearTimeout(thumbnailTimer);
    importLandingThumbDocId.value = '';
    justArrivedDocId.value = '';
    revealRequested = false;
  }

  function prepareImportLanding(id) {
    cancelImportLanding();
    importLandingThumbDocId.value = String(id || '');
  }

  async function beginImportLanding(id) {
    if (!id) return null;
    const current = generation;
    await beforeLocate?.(id);
    if (current !== generation) return null;
    await importLayoutReady();
    const row = findImportRow(root.value, id);
    if (!row) return null;
    revealImportRow(row, scroller.value);
    return waitForImportTarget(() => current === generation
      ? importThumbnailTarget(findImportRow(root.value, id), thumbnailSelector, scroller.value) : null);
  }

  function finishThumbnail(id) {
    if (revealRequested && String(id) === importLandingThumbDocId.value) {
      importLandingThumbDocId.value = '';
      clearTimeout(thumbnailTimer);
    }
  }

  function revealImportLanding() {
    revealRequested = true;
    const id = importLandingThumbDocId.value;
    const thumbnail = findImportRow(root.value, id)?.querySelector(thumbnailSelector);
    const image = thumbnail?.querySelector('img');
    if (!image || image.complete) finishThumbnail(id);
    // Auch ein unterbrochener Bildabruf darf keine dauerhaft weiße Miniatur lassen.
    thumbnailTimer = setTimeout(() => finishThumbnail(id), 2500);
  }

  function resolveImportLanding(id) {
    revealImportLanding();
    justArrivedDocId.value = String(id || '');
    clearTimeout(pulseTimer);
    pulseTimer = setTimeout(() => { justArrivedDocId.value = ''; }, 1900);
  }

  onBeforeUnmount(cancelImportLanding);
  return {
    importLandingThumbDocId, justArrivedDocId, finishThumbnail,
    prepareImportLanding, beginImportLanding, revealImportLanding, resolveImportLanding,
    maskLandingThumb() {}, cancelImportLanding,
  };
}
