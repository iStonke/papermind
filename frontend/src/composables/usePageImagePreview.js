import { computed, nextTick, onScopeDispose, ref, toValue, watch } from 'vue';

export function usePageImagePreview({ source, pageId, thumbnail, rotation, colorMode }) {
  const viewport = ref(null);
  const image = ref(null);
  const viewportSize = ref({ width: 1, height: 1 });
  const imageSize = ref({ width: 200, height: 280 });
  const zoom = ref(1);
  const magnifierEnabled = ref(false);
  const magnifier = ref(null);
  let observer;
  const angle = computed(() => toValue(thumbnail) ? ((Number(toValue(rotation) || 0) % 360) + 360) % 360 : 0);
  const dimensions = computed(() => {
    const quarterTurn = [90, 270].includes(angle.value);
    const width = quarterTurn ? imageSize.value.height : imageSize.value.width;
    const height = quarterTurn ? imageSize.value.width : imageSize.value.height;
    const scale = Math.min(viewportSize.value.width / width, viewportSize.value.height / height) * zoom.value;
    return { width: width * scale, height: height * scale, scale };
  });
  const canvasStyle = computed(() => ({ width: `${Math.max(viewportSize.value.width, dimensions.value.width)}px`, height: `${Math.max(viewportSize.value.height, dimensions.value.height)}px` }));
  const imageStyle = computed(() => ({
    width: `${imageSize.value.width * dimensions.value.scale}px`, height: `${imageSize.value.height * dimensions.value.scale}px`,
    transform: angle.value ? `rotate(${angle.value}deg)` : undefined,
    filter: toValue(thumbnail) && toValue(colorMode) === 'grayscale' ? 'grayscale(1)'
      : toValue(thumbnail) && toValue(colorMode) === 'bw' ? 'grayscale(1) contrast(4)' : undefined,
  }));
  function hideMagnifier() { magnifier.value = null; }
  function onImageLoad() {
    const element = image.value;
    if (element?.naturalWidth && element.naturalHeight) imageSize.value = { width: element.naturalWidth, height: element.naturalHeight };
  }
  async function setZoom(value, point) {
    const element = viewport.value;
    const next = Math.min(3, Math.max(.4, value));
    if (!element || Math.abs(next - zoom.value) < .001) return;
    const rect = element.getBoundingClientRect();
    const x = point ? point.clientX - rect.left : element.clientWidth / 2;
    const y = point ? point.clientY - rect.top : element.clientHeight / 2;
    const relativeX = (element.scrollLeft + x) / Math.max(1, element.scrollWidth);
    const relativeY = (element.scrollTop + y) / Math.max(1, element.scrollHeight);
    hideMagnifier();
    zoom.value = next;
    await nextTick();
    if (viewport.value !== element) return;
    element.scrollLeft = relativeX * element.scrollWidth - x;
    element.scrollTop = relativeY * element.scrollHeight - y;
  }
  function resetZoom() {
    zoom.value = 1;
    hideMagnifier();
    if (viewport.value) { viewport.value.scrollLeft = 0; viewport.value.scrollTop = 0; }
  }
  function onWheel(event) {
    if (!(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    void setZoom(zoom.value * Math.exp(-event.deltaY * .0025), event);
  }
  function onKeydown(event) {
    if (!['+', '=', '-', '0'].includes(event.key) || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.key === '0') resetZoom();
    else void setZoom(event.key === '-' ? zoom.value / 1.12 : zoom.value * 1.12);
  }
  function toggleMagnifier() { magnifierEnabled.value = !magnifierEnabled.value; hideMagnifier(); }
  function onPointerMove(event) {
    const element = image.value;
    if (!magnifierEnabled.value || toValue(thumbnail) || event.pointerType === 'touch' || !element?.complete || !element.naturalWidth) { hideMagnifier(); return; }
    const rect = element.getBoundingClientRect();
    const canvas = element.parentElement.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (x < 0 || y < 0 || x > rect.width || y > rect.height) { hideMagnifier(); return; }
    magnifier.value = { x: event.clientX - canvas.left, y: event.clientY - canvas.top,
      width: rect.width * 2.25, height: rect.height * 2.25, bgX: 110 - x * 2.25, bgY: 66 - y * 2.25 };
  }
  const magnifierStyle = computed(() => magnifier.value ? {
    width: '220px', height: '132px', transform: `translate(${Math.round(magnifier.value.x - 110)}px, ${Math.round(magnifier.value.y - 66)}px)`,
    backgroundImage: `url("${toValue(source)}")`, backgroundSize: `${magnifier.value.width}px ${magnifier.value.height}px`,
    backgroundPosition: `${magnifier.value.bgX}px ${magnifier.value.bgY}px`,
  } : {});
  watch(viewport, element => {
    observer?.disconnect();
    if (!element) return;
    const measure = () => { viewportSize.value = { width: Math.max(1, element.clientWidth), height: Math.max(1, element.clientHeight) }; };
    measure();
    observer = new ResizeObserver(measure);
    observer.observe(element);
  }, { flush: 'post' });
  watch(() => toValue(pageId), resetZoom);
  watch(() => toValue(source), () => { hideMagnifier(); onImageLoad(); }, { flush: 'post' });
  onScopeDispose(() => observer?.disconnect());
  return { viewport, viewportSize, image, zoom, zoomPercent: computed(() => Math.round(zoom.value * 100)),
    canZoomIn: computed(() => zoom.value < 2.999), canZoomOut: computed(() => zoom.value > .401),
    canvasStyle, imageStyle, onImageLoad, resetZoom, zoomIn: () => setZoom(zoom.value * 1.12), zoomOut: () => setZoom(zoom.value / 1.12),
    onWheel, onKeydown, magnifierEnabled, magnifier, magnifierStyle, hideMagnifier, toggleMagnifier, onPointerMove };
}
