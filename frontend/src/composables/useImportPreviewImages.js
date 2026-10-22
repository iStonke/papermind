import { computed, onScopeDispose, ref, watch } from 'vue';
import { pageDisplayRevision } from '../utils/importWorkflow.js';
import { createByteLruCache } from '../utils/byteLruCache.js';

// Source revisions, retained pixels, cancellation and byte accounting share a
// lifecycle here. The scroll controller owns geometry, independently of pixels.
export function useImportPreviewImages({ store, allPagesFlat, selectedPageEntry,
  scannerPreviewFallback, previewScrolling, previewImageSrc, previewImageLoading,
  previewIsThumbnail, thumbnailSizes, pageThumbnailSize, thumbnailRotation,
  renderServerColorPreview, renderLargePreview, hidePreviewMagnifier, diagnostics, sourceElapsed }) {
  const previewPageImages = ref(new Map());
  const previewImageCache = createByteLruCache({ dispose(value) {
    for (const [id, state] of previewPageImages.value) if (state.image === value.image) previewPageImages.value.delete(id);
  } });
  let previewRenderNonce = 0;
  let previewImageContentKey = '';
  let activeDisplay = null;
  const visualIdentity = page => JSON.stringify([page.id, page.sourceFileId, page.pageIndex, page.rotation || 0, page.colorMode || 'auto']);
  function previewContentKey(page) {
    return pageDisplayRevision(page, store.sourceMetaById);
  }
  function pagePreviewState(page) {
    const state = previewPageImages.value.get(page.id);
    if (state?.contentKey === previewContentKey(page)) return state;
    // Keep one already painted active frame during a source refresh. It is not
    // reusable as a cache hit, and disappears on navigation/colour/rotation.
    return page.id === selectedPageEntry.value?.id && activeDisplay?.identity === visualIdentity(page) ? activeDisplay : null;
  }
  function pagePreviewSource(page) {
    const state = pagePreviewState(page);
    return (state && !state.thumbnail ? state.image : '')
      || (scannerPreviewFallback.value?.pageId === page.id ? scannerPreviewFallback.value.url : '')
      || page.thumbUrl || state?.image || '';
  }
  function pagePreviewIsThumbnail(page) {
    return pagePreviewState(page)?.thumbnail ?? true;
  }
  function pagePreviewSize(page) {
    // Keep the thumbnail's established page geometry while its pixels sharpen.
    if (thumbnailSizes.value.has(page.thumbUrl)) {
      const size = pageThumbnailSize(page);
      // Sharp server/PDF images already contain the page rotation.
      return !pagePreviewIsThumbnail(page) && [90, 270].includes(thumbnailRotation(page))
        ? { width: size.height, height: size.width } : size;
    }
    const state = pagePreviewState(page);
    return state?.image === pagePreviewSource(page) && state.size ? state.size : pageThumbnailSize(page);
  }
  function setActivePreview(page, image, thumbnail, size) {
    previewImageSrc.value = image;
    previewIsThumbnail.value = thumbnail;
    if (!image) return;
    previewPageImages.value.delete(page.id);
    const state = { contentKey: previewContentKey(page), identity: visualIdentity(page), image, thumbnail, size };
    activeDisplay = state;
    previewPageImages.value.set(page.id, state);
  }

  function previewCacheKey(page) {
    return `${page.sourceFileId}:${page.pageIndex}:r${Number(page.rotation || 0)}:m${page.colorMode || 'auto'}:${store.sourceMetaById.get(page.sourceFileId)?.sourceRevision || ''}:lg`;
  }
  watch(() => [selectedPageEntry.value?.id, allPagesFlat.value.map(({ page }) => previewContentKey(page)).join('|')], () => {
    const index = allPagesFlat.value.findIndex(({ page }) => page.id === selectedPageEntry.value?.id);
    previewImageCache.protect(allPagesFlat.value.slice(Math.max(0, index - 1), index + 2).map(({ page }) => previewCacheKey(page)));
    const live = new Map(allPagesFlat.value.map(({ page }) => [page.id, previewContentKey(page)]));
    for (const [id, state] of previewPageImages.value) if (live.get(id) !== state.contentKey) previewPageImages.value.delete(id);
  });

  const selectedPreviewRenderKey = computed(() => {
    const pageEntry = selectedPageEntry.value;
    if (!pageEntry) {
      return '';
    }
    return [
      pageEntry.id,
      pageEntry.sourceFileId,
      Number(pageEntry.pageIndex || 0),
      Number(pageEntry.rotation || 0),
      String(pageEntry.colorMode || 'auto'),
      pageEntry.thumbUrl,
      store.sourceMetaById.get(pageEntry.sourceFileId)?.sourceRevision,
      scannerPreviewFallback.value?.pageId === pageEntry.id ? scannerPreviewFallback.value.url : ''
    ].join(':');
  });

  function waitForPreviewIdle(signal) {
    return new Promise(resolve => {
      let timer;
      const finish = () => {
        window.clearTimeout(timer);
        stop();
        signal.removeEventListener('abort', finish);
        resolve();
      };
      const schedule = scrolling => {
        window.clearTimeout(timer);
        if (!scrolling) timer = window.setTimeout(finish, 120);
      };
      const stop = watch(previewScrolling, schedule);
      signal.addEventListener('abort', finish, { once: true });
      if (signal.aborted) finish();
      else schedule(previewScrolling.value);
    });
  }

  watch(
    selectedPreviewRenderKey,
    async (renderKey, _previous, onCleanup) => {
      hidePreviewMagnifier();
      previewRenderNonce += 1;
      const nonce = previewRenderNonce;
      const pageEntry = selectedPageEntry.value ? { ...selectedPageEntry.value } : null;

      if (!renderKey || !pageEntry) {
        previewImageContentKey = '';
        previewImageSrc.value = '';
        previewImageLoading.value = false;
        return;
      }

      const colorMode = String(pageEntry.colorMode || 'auto');
      const contentKey = previewContentKey(pageEntry);
      const scanPreview = scannerPreviewFallback.value?.pageId === pageEntry.id ? scannerPreviewFallback.value.url : '';
      const keepCurrentImage = activeDisplay?.identity === visualIdentity(pageEntry) && Boolean(previewImageSrc.value)
        && (!previewIsThumbnail.value || !scanPreview || previewImageSrc.value === scanPreview);
      previewImageContentKey = contentKey;
      const cacheKey = previewCacheKey(pageEntry);
      const cached = previewImageCache.get(cacheKey);
      if (cached && cached.thumbnail === pageEntry.thumbUrl) {
        setActivePreview(pageEntry, cached.image, false, cached.size);
        previewImageLoading.value = false;
        return;
      }

      if (!keepCurrentImage) {
        const retained = pagePreviewState(pageEntry);
        const keepSharpImage = retained && !retained.thumbnail;
        setActivePreview(pageEntry, keepSharpImage ? retained.image : scanPreview || pageEntry.thumbUrl || '',
          !keepSharpImage, keepSharpImage ? retained.size : undefined);
      }
      previewImageLoading.value = true;
      const request = new AbortController();
      onCleanup(() => request.abort());
      try {
        // Erst nach dem nativen Einrasten nachladen. Ein bereits laufender Auftrag
        // bleibt bei kleinen Layoutkorrekturen erhalten; nur ein Seitenwechsel
        // verwirft ihn. Das verhindert wiederholte Anfragen für dieselbe Seite.
        await waitForPreviewIdle(request.signal);
        if (request.signal.aborted) return;
        const networkStarted = performance.now();
        const serverPreview = await renderServerColorPreview(pageEntry, colorMode, request.signal);
        const networkMs = performance.now() - networkStarted;
        const browserStarted = performance.now();
        if (request.signal.aborted) return;
        const rendered = serverPreview
          || await renderLargePreview(pageEntry, 1400, Number(pageEntry.rotation || 0), request.signal);
        if (nonce !== previewRenderNonce) return;
        if (rendered) {
          const image = new Image();
          image.src = rendered;
          await image.decode();
          if (previewScrolling.value) await waitForPreviewIdle(request.signal);
          if (request.signal.aborted || nonce !== previewRenderNonce) return;
          const size = { width: image.naturalWidth, height: image.naturalHeight };
          diagnostics.record('preview_render', { network_ms: networkMs, browser_ms: performance.now() - browserStarted });
          diagnostics.once(`sharp:${pageEntry.sourceFileId}`, 'first_sharp_preview', { duration_ms: sourceElapsed(pageEntry.sourceFileId), cache_bytes: previewImageCache.bytes });
          setActivePreview(pageEntry, rendered, false, size);
          previewImageCache.set(cacheKey, { image: rendered, thumbnail: pageEntry.thumbUrl, size });
        }
      } catch {
        // Das letzte gültige Bild bleibt auch bei einer fehlerhaften Antwort sichtbar.
      } finally {
        if (nonce === previewRenderNonce) previewImageLoading.value = false;
      }
    },
    { immediate: true }
  );

  function clear() { previewRenderNonce++; previewImageCache.clear(); previewPageImages.value.clear(); previewImageContentKey = ''; activeDisplay = null; }
  function invalidate(sourceId) {
    for (const { page } of allPagesFlat.value) if (page.sourceFileId === sourceId) previewPageImages.value.delete(page.id);
    for (const key of [...previewImageCache.keys()]) if (key.startsWith(`${sourceId}:`)) previewImageCache.delete(key);
  }
  onScopeDispose(clear);
  return { pagePreviewSource, pagePreviewIsThumbnail, pagePreviewSize, clear, invalidate, stats: () => ({ bytes: previewImageCache.bytes, budget: previewImageCache.budget }) };
}
