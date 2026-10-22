import { onScopeDispose, toRaw, toValue } from 'vue';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import { PDF_WORKER_SRC } from '../utils/pdfWorker.js';
import { createPdfSourcePool } from '../utils/pdfSourcePool.js';
import { convertImportPreviewPixels } from '../utils/importPreviewPixels.js';
import { scanImageQuality } from '../utils/scanImageQuality.js';

GlobalWorkerOptions.workerSrc = PDF_WORKER_SRC;
export function useImportPdfRenderer(files) {
  const pool = createPdfSourcePool(bytes => getDocument({ data: bytes }).promise);
  const thumbnailQuality = new WeakMap();
  const localKeys = new WeakMap();
  let nextKey = 0;
  function key(file) { if (!localKeys.has(file)) localKeys.set(file, `local-${++nextKey}`); return localKeys.get(file); }
  async function renderPdfThumbnails(file, pageCount) {
    if (!(file instanceof File) || pageCount <= 0) return [];
    const lease = await pool.acquire(key(file), toRaw(file));
    const thumbs = [], quality = [];
    try {
      for (let number = 1; number <= Math.min(12, Number(pageCount), lease.pdf.numPages); number++) {
        let canvas, page;
        try {
          page = await lease.pdf.getPage(number);
          const base = page.getViewport({ scale: 1 });
          const viewport = page.getViewport({ scale: 480 / Math.max(1, base.width) });
          canvas = document.createElement('canvas');
          const context = canvas.getContext('2d', { alpha: false });
          if (!context) { thumbs.push(''); continue; }
          canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
          await page.render({ canvasContext: context, viewport }).promise;
          quality.push(scanImageQuality(context.getImageData(0, 0, canvas.width, canvas.height)));
          thumbs.push(canvas.toDataURL('image/webp', .82));
        } catch { thumbs.push(''); }
        finally { if (canvas) canvas.width = canvas.height = 0; page?.cleanup(); }
      }
    } finally { lease.release(); }
    thumbnailQuality.set(file, quality);
    return thumbs;
  }
  async function renderLargePreview(entry, targetLongEdge = 1400, rotation = 0, signal) {
    const file = toRaw(toValue(files).get(entry?.sourceFileId));
    if (!(file instanceof File) || signal?.aborted) return '';
    let lease, task, canvas, page;
    const abort = () => { try { task?.cancel(); } catch { /* completed */ } };
    signal?.addEventListener('abort', abort, { once: true });
    try {
      lease = await pool.acquire(key(file), file);
      if (signal?.aborted) return '';
      page = await lease.pdf.getPage(Number(entry.pageIndex || 0) + 1);
      if (signal?.aborted) return '';
      const angle = ((Number(rotation) % 360) + 360) % 360;
      const base = page.getViewport({ scale: 1, rotation: angle });
      const viewport = page.getViewport({ scale: targetLongEdge / Math.max(1, base.width, base.height), rotation: angle });
      canvas = document.createElement('canvas');
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) return '';
      canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
      task = page.render({ canvasContext: context, viewport });
      await task.promise;
      if (signal?.aborted) return '';
      if (['grayscale', 'bw'].includes(entry.colorMode)) {
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
        convertImportPreviewPixels(pixels.data, entry.colorMode);
        context.putImageData(pixels, 0, 0);
      }
      return canvas.toDataURL('image/webp', .9);
    } catch { return ''; }
    finally {
      signal?.removeEventListener('abort', abort);
      if (canvas) canvas.width = canvas.height = 0;
      page?.cleanup();
      lease?.release();
    }
  }
  onScopeDispose(() => pool.close());
  return { renderPdfThumbnails, renderLargePreview, thumbnailQuality, clear: () => pool.clear(), invalidate: id => { const file = toRaw(toValue(files).get(id)); if (file) pool.invalidate(key(file)); } };
}
