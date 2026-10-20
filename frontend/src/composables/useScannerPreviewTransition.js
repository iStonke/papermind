import { computed, nextTick, onScopeDispose, ref, shallowRef, toValue, watch } from 'vue';
import { onApiSessionReset } from '../api/session.js';

// Live-URLs enden mit dem Scan. Eine Kopie im Arbeitsspeicher bleibt unabhängig
// davon sichtbar, bis die eigentliche Seitenvorschau geladen ist.
export function useScannerPreviewTransition({ scanner, active, candidateUrl, open, empty, firstPage, acceptsPage, getThumbnail, getPreview, isPreviewReady, animationsEnabled }) {
  const previewUrl = ref('');
  const progress = ref(0);
  const sourceElement = ref(null);
  const flightElement = ref(null);
  const flight = shallowRef(null);
  const thumbnailFallback = shallowRef(null);
  const previewFallback = shallowRef(null);
  const finalizing = computed(() => Boolean(previewUrl.value && (progress.value >= 100 || !toValue(active))));
  let loadId = 0;
  let requestedUrl = '';
  let controller = null;
  const frameUrls = new Set();
  const decodingUrls = new Set();
  let raf = 0;
  let flightStartedAt = null;
  let decodedPreview = null;
  let disposed = false;

  function releaseUnusedFrames() {
    if (!frameUrls.size) return;
    void nextTick(() => {
      const used = new Set([previewUrl.value, flight.value?.url, thumbnailFallback.value?.url, previewFallback.value?.url, ...decodingUrls]);
      for (const url of frameUrls) if (!used.has(url)) {
        URL.revokeObjectURL(url);
        frameUrls.delete(url);
      }
    });
  }

  function finishFlight() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    flightStartedAt = null;
    flight.value = null;
    if (decodedPreview?.fallback === previewFallback.value
      && decodedPreview.image.isConnected && decodedPreview.image.complete && decodedPreview.image.naturalWidth
      && (decodedPreview.image.currentSrc || decodedPreview.image.src) === decodedPreview.url) previewFallback.value = null;
    decodedPreview = null;
    releaseUnusedFrames();
  }

  function reset({ clearThumbnail = false } = {}) {
    loadId++;
    requestedUrl = '';
    controller?.abort();
    controller = null;
    previewUrl.value = '';
    progress.value = 0;
    finishFlight();
    if (clearThumbnail) {
      thumbnailFallback.value = null;
      previewFallback.value = null;
    }
    releaseUnusedFrames();
  }

  async function loadFrame(url) {
    requestedUrl = url;
    const id = ++loadId;
    controller?.abort();
    const request = new AbortController();
    controller = request;
    let frozenUrl = '';
    try {
      const response = await fetch(url, { signal: request.signal, cache: 'no-store' });
      if (!response.ok) return;
      const blob = await response.blob();
      if (id !== loadId || disposed) return;
      frozenUrl = URL.createObjectURL(blob);
      frameUrls.add(frozenUrl);
      decodingUrls.add(frozenUrl);
      const image = new Image();
      image.decoding = 'async';
      image.src = frozenUrl;
      await image.decode();
      // Auch ein gerade fertig geladenes Bild darf nach dem Entfernen der
      // Live-URL ankommen. Nur ein neuer Scan/Sitzungswechsel verwirft es.
      if (id === loadId && !disposed) previewUrl.value = frozenUrl;
    } catch {
      // Ein unvollständiger Frame ersetzt nie das letzte gültige Bild.
    } finally {
      decodingUrls.delete(frozenUrl);
      if (controller === request) controller = null;
      releaseUnusedFrames();
    }
  }

  watch(
    () => [toValue(scanner)?.id, toValue(active), toValue(scanner)?.scan_progress, toValue(candidateUrl), toValue(open)],
    ([id, scanning, rawProgress, url, visible], previous = []) => {
      const [oldId, wasScanning] = previous;
      if (!visible) { reset({ clearThumbnail: true }); return; }
      const value = rawProgress == null ? null : Number(rawProgress);
      const newPage = scanning && Number.isFinite(value) && value < progress.value;
      if (id !== oldId || (scanning && !wasScanning) || newPage) reset({ clearThumbnail: id !== oldId });
      if (Number.isFinite(value)) progress.value = Math.max(0, Math.min(100, Math.round(value)));
      if (url && url !== requestedUrl) void loadFrame(url);
      // Kein Zurücksetzen bei fehlender URL/fehlendem Fortschritt: zwischen
      // Scannerabschluss und Inbox-Eingang gibt es noch keine Miniatur.
    },
    { immediate: true }
  );

  function motionEnabled() {
    return toValue(animationsEnabled) !== false
      && !document.querySelector('.pm-no-animations')
      && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function flightStep(now) {
    raf = 0;
    const state = flight.value;
    const element = flightElement.value;
    const target = state?.pageId && getPreview(state.pageId);
    if (!state || !element || !target) { finishFlight(); return; }
    if (!motionEnabled()) { finishFlight(); return; }
    if (flightStartedAt == null) flightStartedAt = now;
    const t = Math.min(1, (now - flightStartedAt) / 400);
    const eased = 1 - (1 - t) ** 3;
    const rect = target.getBoundingClientRect();
    const interpolate = key => state.origin[key] + (rect[key] - state.origin[key]) * eased;
    // Das Ziel wird pro Frame gemessen: auch während sich das Dialogfenster
    // verbreitert, endet das Blatt genau auf der großen Seitenvorschau.
    Object.assign(element.style, {
      transform: `translate3d(${interpolate('left')}px, ${interpolate('top')}px, 0)`,
      width: `${interpolate('width')}px`, height: `${interpolate('height')}px`,
      borderRadius: `${10 - 6 * eased}px`,
      boxShadow: `0 ${18 * (1 - eased)}px ${34 * (1 - eased)}px rgba(15, 23, 42, ${0.16 * (1 - eased)})`,
    });
    if (t >= 1) finishFlight();
    else raf = requestAnimationFrame(flightStep);
  }

  async function attachPreview() {
    const state = flight.value;
    const page = toValue(firstPage);
    if (!state || !page || state.pageId) return;
    // Parallel hochgeladene PDFs dürfen kein Vorschaubild des Scanners erben.
    if (!acceptsPage(page)) { finishFlight(); return; }
    // Der Fallback gehört zur Seite, nicht zum Scanner. Er bleibt auch bei
    // langsamer oder fehlgeschlagener Miniatur-Anfrage als Vorschau erhalten.
    thumbnailFallback.value = { pageId: page.id, url: state.url };
    previewFallback.value = { pageId: page.id, url: state.url };
    decodedPreview = null;
    flight.value = { ...state, pageId: page.id };
    // Ab jetzt gehört dieses Bild zur importierten Seite. Es darf beim
    // späteren Entfernen aller Seiten nicht wieder im Startbildschirm stehen.
    previewUrl.value = '';
    loadId++;
    controller?.abort();
    controller = null;
    await nextTick();
    if (flight.value?.pageId !== page.id || disposed) return;
    const target = getPreview(page.id);
    if (!target) { finishFlight(); return; }
    const image = getThumbnail(page.id)?.querySelector('.import-staging-page__thumb');
    if (image?.complete && image.naturalWidth) void thumbnailLoaded(page.id, image);
    if (isPreviewReady(page.id) && target.complete && target.naturalWidth) void previewLoaded(page.id, target);
    if (!motionEnabled()) finishFlight();
    else if (!raf) raf = requestAnimationFrame(flightStep);
  }

  watch(empty, (isEmpty, wasEmpty) => {
    if (isEmpty) {
      finishFlight();
      thumbnailFallback.value = null;
      previewFallback.value = null;
      releaseUnusedFrames();
      return;
    }
    const source = sourceElement.value;
    if (!wasEmpty || !toValue(open) || !previewUrl.value || !source) return;
    const rect = source.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const origin = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    flight.value = { url: previewUrl.value, origin, pageId: '', style: {
      transform: `translate3d(${rect.left}px, ${rect.top}px, 0)`,
      width: `${rect.width}px`, height: `${rect.height}px`,
    } };
    void attachPreview();
  }, { flush: 'pre' });

  watch(() => toValue(firstPage)?.id, () => {
    const state = flight.value;
    if (state?.pageId && state.pageId !== toValue(firstPage)?.id) finishFlight();
    else void attachPreview();
  }, { flush: 'post' });

  async function thumbnailLoaded(pageId, image) {
    const fallback = thumbnailFallback.value;
    if (fallback?.pageId !== pageId) return;
    const url = image.currentSrc || image.src;
    try { await image.decode(); } catch { return; }
    if (thumbnailFallback.value === fallback && image.isConnected && (image.currentSrc || image.src) === url) {
      thumbnailFallback.value = null;
      releaseUnusedFrames();
    }
  }

  async function previewLoaded(pageId, image) {
    const fallback = previewFallback.value;
    const url = image.currentSrc || image.src;
    if (fallback?.pageId !== pageId || url === fallback.url || !isPreviewReady(pageId)) return;
    try { await image.decode(); } catch { return; }
    if (previewFallback.value === fallback && image.isConnected && (image.currentSrc || image.src) === url) {
      // Das hochaufgelöste Bild blendet erst nach der Landung ein. Bis dahin
      // verwendet die Vergrößerung dieselbe Originaldatei wie die Scanvorschau.
      if (flight.value?.pageId === pageId) decodedPreview = { fallback, image, url };
      else previewFallback.value = null;
      releaseUnusedFrames();
    }
  }

  const stopSessionListener = onApiSessionReset(() => reset({ clearThumbnail: true }));
  // Bei einer während des Flugs geänderten Ansicht direkt am aktuellen Ziel
  // einblenden; kein losgelöstes Blatt über einem geschlossenen Dialog lassen.
  window.addEventListener('resize', finishFlight);
  window.addEventListener('scroll', finishFlight, true);
  onScopeDispose(() => {
    disposed = true;
    reset({ clearThumbnail: true });
    stopSessionListener();
    window.removeEventListener('resize', finishFlight);
    window.removeEventListener('scroll', finishFlight, true);
  });

  return { previewUrl, progress, finalizing, sourceElement, flightElement, flight, thumbnailFallback, thumbnailLoaded, previewFallback, previewLoaded, reset };
}
