import { computed, nextTick, onScopeDispose, ref, shallowReactive, toValue, watch } from 'vue';

// Native scrolling owns page movement. Selection follows the viewport; only
// explicit navigation scrolls to a page, so the two cannot pull each other back.
export function useContinuousPagePreview({ pages, pageId, source, thumbnail, size, onVisiblePage }) {
  const viewport = ref(null);
  const viewportSize = ref({ width: 1, height: 1 });
  const zoom = ref(1);
  const scrolling = ref(false);
  const adjusting = ref(false);
  const magnifierEnabled = ref(false);
  const magnifier = ref(null);
  const pageElements = new Map();
  const imageElements = shallowReactive(new Map());
  const imageSizes = shallowReactive(new Map());
  const image = computed(() => imageElements.get(toValue(pageId)) || null);
  const frames = new Set();
  let observer;
  let visibilityObserver;
  const nearViewport = shallowReactive(new Set());
  const nearbyIds = computed(() => {
    const list = toValue(pages);
    const index = list.findIndex(page => page.id === toValue(pageId));
    return new Set(list.slice(Math.max(0, index - 2), index + 3).map(page => page.id));
  });
  function shouldLoad(id) { return nearbyIds.value.has(id) || nearViewport.has(id); }
  let syncFrame = 0;
  let navigation = 0;
  let navigating = false;
  let zooming = false;
  let scrollSelection = null;
  let disposed = false;
  let scrollEndTimer = 0;

  function frame(callback) {
    const id = requestAnimationFrame(() => { frames.delete(id); if (!disposed) callback(); });
    frames.add(id);
    return id;
  }
  const layouts = computed(() => toValue(pages).map(page => {
    const loaded = imageSizes.get(page.id);
    // Sharpening an image must not resize its page or move the snap position.
    const dimensions = size(page) || (loaded?.url === source(page) ? loaded : null);
    const width = Math.max(1, Number(dimensions?.width) || 200);
    const height = Math.max(1, Number(dimensions?.height) || 280);
    const angle = thumbnail(page) ? ((Number(page.rotation || 0) % 360) + 360) % 360 : 0;
    const turned = [90, 270].includes(angle);
    const orientedWidth = turned ? height : width;
    const orientedHeight = turned ? width : height;
    const scale = Math.min(Math.max(1, viewportSize.value.width - 24) / orientedWidth,
      Math.max(1, viewportSize.value.height - 24) / orientedHeight) * zoom.value;
    return { id: page.id, width: orientedWidth * scale, height: orientedHeight * scale,
      imageWidth: width * scale, imageHeight: height * scale, angle };
  }));
  const layoutById = computed(() => new Map(layouts.value.map(layout => [layout.id, layout])));
  const canvasStyle = computed(() => ({
    width: `${Math.max(viewportSize.value.width, ...layouts.value.map(page => page.width + 24))}px`,
    minHeight: `${viewportSize.value.height}px`,
    paddingTop: `${(layouts.value[0]?.height > viewportSize.value.height ? 0 : Math.max(12, (viewportSize.value.height - (layouts.value[0]?.height || 0)) / 2))}px`,
    paddingBottom: `${(layouts.value.at(-1)?.height > viewportSize.value.height ? 0 : Math.max(12, (viewportSize.value.height - (layouts.value.at(-1)?.height || 0)) / 2))}px`,
  }));
  function pageStyle(page) {
    const layout = layoutById.value.get(page.id);
    return layout ? { width: `${layout.width}px`, height: `${layout.height}px` } : {};
  }
  function imageStyle(page) {
    const layout = layoutById.value.get(page.id);
    return layout ? { width: `${layout.imageWidth}px`, height: `${layout.imageHeight}px`,
      transform: layout.angle ? `rotate(${layout.angle}deg)` : undefined,
      filter: thumbnail(page) && page.colorMode === 'grayscale' ? 'grayscale(1)'
        : thumbnail(page) && page.colorMode === 'bw' ? 'grayscale(1) contrast(4)' : undefined } : {};
  }
  function setPageElement(id, element) {
    const previous = pageElements.get(id);
    if (previous === element) return;
    if (previous) visibilityObserver?.unobserve(previous);
    if (element) { pageElements.set(id, element); visibilityObserver?.observe(element); }
    else { pageElements.delete(id); nearViewport.delete(id); }
  }
  function setImageElement(id, element) {
    if (element) imageElements.set(id, element);
    else imageElements.delete(id);
  }
  function onImageLoad(id, element) {
    if (!element?.naturalWidth || !element.naturalHeight) return;
    const next = { url: element.getAttribute('src'), width: element.naturalWidth, height: element.naturalHeight };
    const previous = imageSizes.get(id);
    if (previous?.url !== next.url || previous.width !== next.width || previous.height !== next.height) imageSizes.set(id, next);
  }
  function coordinateScale(element) {
    const rect = element.getBoundingClientRect();
    return { x: rect.width / Math.max(1, element.offsetWidth), y: rect.height / Math.max(1, element.offsetHeight) };
  }
  function nearestPage(y) {
    let nearest;
    let distance = Infinity;
    for (const [id, element] of pageElements) {
      if (!element.isConnected) continue;
      const rect = element.getBoundingClientRect();
      const next = y < rect.top ? rect.top - y : y > rect.bottom ? y - rect.bottom : 0;
      if (next < distance) { nearest = { id, element, rect }; distance = next; }
    }
    return nearest;
  }
  function hideMagnifier() { magnifier.value = null; }
  function scheduleVisiblePage() {
    if (syncFrame) return;
    syncFrame = frame(() => {
      syncFrame = 0;
      if (navigating || !viewport.value || !toValue(pageId)) return;
      const rect = viewport.value.getBoundingClientRect();
      const nearest = nearestPage(rect.top + viewport.value.clientHeight * coordinateScale(viewport.value).y / 2);
      if (nearest && nearest.id !== toValue(pageId)) {
        scrollSelection = nearest.id;
        onVisiblePage(nearest.id);
      }
    });
  }
  function onScrollEnd() {
    window.clearTimeout(scrollEndTimer);
    scrolling.value = false;
    scheduleVisiblePage();
  }
  function onScroll() {
    hideMagnifier();
    if (navigating) return;
    scrolling.value = true;
    window.clearTimeout(scrollEndTimer);
    // scrollend follows native inertia and snapping. The timer also supports
    // browsers without that event and is renewed throughout the movement.
    scrollEndTimer = window.setTimeout(onScrollEnd, 180);
  }
  function captureAnchor(point) {
    const element = viewport.value;
    if (!element) return null;
    const view = element.getBoundingClientRect();
    const scale = coordinateScale(element);
    const x = point?.clientX ?? view.left + element.clientWidth * scale.x / 2;
    const y = point?.clientY ?? view.top + element.clientHeight * scale.y / 2;
    const nearest = nearestPage(y);
    return nearest ? { id: nearest.id, x: (x - nearest.rect.left) / Math.max(1, nearest.rect.width),
      y: (y - nearest.rect.top) / Math.max(1, nearest.rect.height), clientX: x, clientY: y } : null;
  }
  function restoreAnchor(anchor) {
    const element = viewport.value;
    const page = anchor && pageElements.get(anchor.id);
    if (!element || !page) return;
    const rect = page.getBoundingClientRect();
    const scale = coordinateScale(element);
    element.scrollLeft += (rect.left + rect.width * anchor.x - anchor.clientX) / scale.x;
    element.scrollTop += (rect.top + rect.height * anchor.y - anchor.clientY) / scale.y;
  }
  function settleNavigation(id) {
    frame(() => frame(() => {
      if (navigation !== id) return;
      navigating = false;
      scheduleVisiblePage();
    }));
  }
  async function scrollToPage(id) {
    if (!id) return;
    adjusting.value = false;
    const current = ++navigation;
    navigating = true;
    hideMagnifier();
    await nextTick();
    if (disposed || current !== navigation) return;
    const element = viewport.value;
    const page = pageElements.get(id);
    if (element && page) {
      const view = element.getBoundingClientRect();
      const rect = page.getBoundingClientRect();
      const scale = coordinateScale(element);
      element.scrollTop += (rect.top - view.top) / scale.y - Math.max(12, (element.clientHeight - rect.height / scale.y) / 2);
    }
    settleNavigation(current);
  }
  async function setZoom(value, point) {
    adjusting.value = false;
    const next = Math.min(3, Math.max(.4, value));
    if (!viewport.value || Math.abs(next - zoom.value) < .001) return;
    const anchor = captureAnchor(point);
    const current = ++navigation;
    navigating = true;
    zooming = true;
    hideMagnifier();
    zoom.value = next;
    await nextTick();
    if (disposed || current !== navigation) { zooming = false; return; }
    restoreAnchor(anchor);
    zooming = false;
    settleNavigation(current);
  }
  function resetZoom() {
    if (Math.abs(zoom.value - 1) < .001) void scrollToPage(toValue(pageId));
    else void setZoom(1);
  }
  function onWheel(event) {
    if (!event.ctrlKey && !event.metaKey) {
      if (adjusting.value) { navigation++; adjusting.value = false; navigating = false; }
      return;
    }
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? (viewport.value?.clientHeight || 800) : 1;
    const delta = Number(event.deltaY) * unit;
    if (!Number.isFinite(delta) || delta === 0) return;
    event.preventDefault();
    void setZoom(zoom.value * Math.exp(-delta * .0025), event);
  }
  function onKeydown(event) {
    if (!['+', '=', '-', '0'].includes(event.key) || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.key === '0') resetZoom();
    else void setZoom(event.key === '-' ? zoom.value / 1.12 : zoom.value * 1.12);
  }
  function toggleMagnifier() { magnifierEnabled.value = !magnifierEnabled.value; hideMagnifier(); }
  function onPointerMove(event, page) {
    const element = event.currentTarget;
    if (!magnifierEnabled.value || thumbnail(page) || event.pointerType === 'touch' || !element?.naturalWidth) { hideMagnifier(); return; }
    const rect = element.getBoundingClientRect();
    const parent = element.parentElement.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (x < 0 || y < 0 || x > rect.width || y > rect.height) { hideMagnifier(); return; }
    magnifier.value = { pageId: page.id, url: source(page), x: event.clientX - parent.left, y: event.clientY - parent.top,
      width: rect.width * 2.25, height: rect.height * 2.25, bgX: 110 - x * 2.25, bgY: 66 - y * 2.25 };
  }
  const magnifierStyle = computed(() => magnifier.value ? {
    width: '220px', height: '132px', transform: `translate(${Math.round(magnifier.value.x - 110)}px, ${Math.round(magnifier.value.y - 66)}px)`,
    backgroundImage: `url("${magnifier.value.url}")`, backgroundSize: `${magnifier.value.width}px ${magnifier.value.height}px`,
    backgroundPosition: `${magnifier.value.bgX}px ${magnifier.value.bgY}px`,
  } : {});
  watch(viewport, element => {
    observer?.disconnect();
    visibilityObserver?.disconnect();
    nearViewport.clear();
    if (!element) {
      window.clearTimeout(scrollEndTimer);
      scrolling.value = false;
      navigation++;
      navigating = false;
      zooming = false;
      adjusting.value = false;
      zoom.value = 1;
      imageSizes.clear();
      return;
    }
    const measure = () => { viewportSize.value = { width: Math.max(1, element.clientWidth), height: Math.max(1, element.clientHeight) }; };
    measure();
    observer = new ResizeObserver(measure);
    observer.observe(element);
    visibilityObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        const id = entry.target.dataset.previewPageId;
        if (entry.isIntersecting) nearViewport.add(id); else nearViewport.delete(id);
      }
    }, { root: element, rootMargin: '100% 0px' });
    for (const page of pageElements.values()) visibilityObserver.observe(page);
  }, { flush: 'post' });
  watch(() => toValue(pageId), id => {
    hideMagnifier();
    if (id !== scrollSelection) void scrollToPage(id);
    scrollSelection = null;
  }, { flush: 'post' });
  watch(() => layouts.value.map(page => `${page.id}:${page.width.toFixed(3)}:${page.height.toFixed(3)}`).join('|'), async () => {
    if (zooming || navigating || scrolling.value) return;
    const anchor = captureAnchor();
    if (!anchor) return;
    const current = ++navigation;
    navigating = true;
    // WebKit otherwise re-snaps to the old numerical offset after a reorder.
    // Suspend snapping only for the layout transaction, retaining the same page.
    adjusting.value = true;
    await nextTick();
    if (disposed || current !== navigation) return;
    restoreAnchor(anchor);
    frame(() => frame(() => {
      if (current !== navigation) return;
      restoreAnchor(anchor);
      adjusting.value = false;
      navigating = false;
      scheduleVisiblePage();
    }));
  });
  watch(() => toValue(pages).map(page => [page.id, source(page)]), entries => {
    const used = new Map(entries);
    for (const [id, dimensions] of imageSizes) if (used.get(id) !== dimensions.url) imageSizes.delete(id);
  });
  onScopeDispose(() => { disposed = true; window.clearTimeout(scrollEndTimer); observer?.disconnect(); visibilityObserver?.disconnect(); for (const id of frames) cancelAnimationFrame(id); frames.clear(); });
  return { viewport, image, zoom, scrolling, adjusting, zoomPercent: computed(() => Math.round(zoom.value * 100)),
    canZoomIn: computed(() => zoom.value < 2.999), canZoomOut: computed(() => zoom.value > .401),
    canvasStyle, pageStyle, imageStyle, shouldLoad, setPageElement, setImageElement, onImageLoad, onScroll, onScrollEnd, scrollToPage,
    resetZoom, zoomIn: () => setZoom(zoom.value * 1.12), zoomOut: () => setZoom(zoom.value / 1.12), onWheel, onKeydown,
    magnifierEnabled, magnifier, magnifierStyle, hideMagnifier, toggleMagnifier, onPointerMove };
}
