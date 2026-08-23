<template>
  <Teleport to="body">
    <div class="import-flight-layer" aria-hidden="true">
      <div ref="cardEl" class="import-flight-card" :style="cardStyle">
        <div
          v-if="origin.visualClone"
          ref="cloneHostEl"
          class="import-flight-card__clone-host"
        />
        <img
          v-else-if="thumbUrl"
          ref="thumbEl"
          :src="thumbUrl"
          class="import-flight-card__thumb"
          :style="thumbStyle"
          alt=""
          draggable="false"
        />
        <div v-else class="import-flight-card__fallback">
          <v-icon size="34">{{ fallbackIcon }}</v-icon>
        </div>
        <span ref="sheenEl" class="import-flight-card__sheen" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  // Ursprungs-Rechteck (Dialog-Thumbnail), in Viewport-Koordinaten.
  origin: { type: Object, required: true }, // { left, top, width, height }
  // Ziel-Rechteck (Landezeile oder Sidebar-Ziel), in Viewport-Koordinaten.
  // `vanish: true` schrumpft die Karte am Ziel vollständig in den Zielpunkt.
  // Darf zunächst null sein: dann HÄLT die Karte deckungsgleich über dem
  // Dialog-Thumbnail (Hero-Übergang), bis das Ziel gesetzt wird und sie fliegt.
  target: { type: Object, default: null },
  thumbUrl: { type: String, default: '' },
  // CSS-Filter des Import-Farbmodus (z. B. 'grayscale(1) contrast(4)' für S/W),
  // damit die fliegende Miniatur exakt wie die Import-Vorschau aussieht.
  thumbFilter: { type: String, default: 'none' },
  fallbackIcon: { type: String, default: 'mdi-file-document-outline' }
});

const emit = defineEmits(['landed', 'approaching']);

const cardEl = ref(null);
const thumbEl = ref(null);
const sheenEl = ref(null);
const cloneHostEl = ref(null);
let mountedVisualClone = null;

function finite(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function frame(rect, fallback = {}) {
  return {
    left: finite(rect?.left, finite(fallback.left)),
    top: finite(rect?.top, finite(fallback.top)),
    width: Math.max(finite(rect?.width, finite(fallback.width, 1)), 1),
    height: Math.max(finite(rect?.height, finite(fallback.height, 1)), 1),
    borderRadius: Math.max(finite(rect?.borderRadius, finite(fallback.borderRadius, 0)), 0),
    borderWidth: Math.max(finite(rect?.borderWidth, finite(fallback.borderWidth, 0)), 0)
  };
}

const originFrame = computed(() => frame(props.origin));
const hasVisualClone = computed(() => Boolean(props.origin?.visualClone));

function makeTransform(left, top, rotate = 0, lift = 1) {
  return `translate3d(${left.toFixed(2)}px, ${top.toFixed(2)}px, 0) rotate(${rotate.toFixed(2)}deg) scale(${lift.toFixed(4)})`;
}

const cardStyle = computed(() => {
  const start = originFrame.value;
  const clonedVisual = hasVisualClone.value;
  return {
    width: `${start.width}px`,
    height: `${start.height}px`,
    transform: makeTransform(start.left, start.top),
    borderRadius: `${start.borderRadius}px`,
    borderWidth: clonedVisual ? '0px' : `${start.borderWidth}px`,
    borderStyle: props.origin?.borderStyle || 'solid',
    borderColor: props.origin?.borderColor || 'transparent',
    backgroundColor: clonedVisual ? 'transparent' : (props.origin?.backgroundColor || 'transparent'),
    boxShadow: clonedVisual ? 'none' : (props.origin?.boxShadow || 'none'),
    outlineWidth: `${Math.max(finite(props.origin?.outlineWidth), 0)}px`,
    outlineStyle: props.origin?.outlineStyle || 'solid',
    outlineColor: props.origin?.outlineColor || 'transparent',
    outlineOffset: `${finite(props.origin?.outlineOffset)}px`,
    '--flight-border-width': clonedVisual ? '0px' : `${start.borderWidth}px`,
    '--flight-border-double': clonedVisual ? '0px' : `${start.borderWidth * 2}px`
  };
});

const thumbStyle = computed(() => ({
  objectFit: props.origin?.imageFit || 'contain',
  objectPosition: props.origin?.imagePosition || 'center center',
  filter: props.thumbFilter,
  transform: props.origin?.thumbTransform || 'none'
}));

function centerOf(rect) {
  return {
    x: Number(rect.left) + Number(rect.width) / 2,
    y: Number(rect.top) + Number(rect.height) / 2
  };
}

const DURATION = 950;

function prefersReducedMotion() {
  try {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches || false;
  } catch {
    return false;
  }
}

// Sanftes Beschleunigen/Abbremsen für die Bahn.
function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

let rafId = 0;
let startTs = 0;
let done = false;
let approachingEmitted = false;
// Ab hier gilt die Karte als „im Endanflug": sie liegt bereits klein über der
// Ziel-Thumbnailspalte. Erst jetzt maskiert die Liste das echte Vorschaubild
// (weißer Platzhalter, von der Karte verdeckt) – nicht schon während des Flugs.
const APPROACH_THRESHOLD = 0.8;

function finish() {
  if (done) return;
  done = true;
  emit('landed');
}

function step(ts) {
  if (!startTs) startTs = ts;
  const raw = Math.min((ts - startTs) / DURATION, 1);
  if (!approachingEmitted && raw >= APPROACH_THRESHOLD) {
    approachingEmitted = true;
    emit('approaching');
  }
  const t = easeInOut(raw);

  const p0 = centerOf(props.origin);
  const p1 = centerOf(props.target);
  const start = originFrame.value;
  const end = frame(props.target, start);
  const vanishAtTarget = Boolean(props.target?.vanish);

  // Bogen: Kontrollpunkt hoch über der Verbindungslinie – bewusst großzügig,
  // damit der Weg zelebriert wird (Safari-Dock-Anmutung, nur weiter geschwungen).
  const span = Math.hypot(p1.x - p0.x, p1.y - p0.y);
  const arc = Math.min(Math.max(span * 0.42, 90), 320);
  const cx = (p0.x + p1.x) / 2;
  const cy = Math.min(p0.y, p1.y) - arc;

  // Quadratische Bézier-Interpolation der Position.
  const mt = 1 - t;
  const x = mt * mt * p0.x + 2 * mt * t * cx + t * t * p1.x;
  const y = mt * mt * p0.y + 2 * mt * t * cy + t * t * p1.y;

  // Breite und Höhe separat morphen. Damit liegen sowohl der 3:4-Rahmen im
  // Importdialog als auch das leicht andere Listenformat an den Endpunkten
  // pixelgenau – ohne den bisherigen Höhenfehler durch eine Einheits-Skalierung.
  // Beim Sidebar-Ziel separat und gleichmäßig skalieren: Durch die langsam
  // auslaufende Bahnkurve bleibt die Seite so bis direkt vor dem Icon erkennbar,
  // statt schon weit vorher winzig zu werden. Am Ziel erreicht sie exakt 0 px.
  const sizeT = vanishAtTarget ? raw : t;
  const targetWidth = vanishAtTarget ? 0 : end.width;
  const targetHeight = vanishAtTarget ? 0 : end.height;
  const width = start.width + (targetWidth - start.width) * sizeT;
  const height = start.height + (targetHeight - start.height) * sizeT;

  // Sanftes „Abheben“ zu Beginn: kurzer Skalier-Impuls in den ersten ~22%.
  const lift = 1 + 0.1 * Math.sin(Math.min(raw / 0.22, 1) * Math.PI);
  // Leichtes Kippen entlang der Flugrichtung, kurz vor der Landung ausrichten.
  const rotate = Math.sin(raw * Math.PI) * 7 * (p1.x >= p0.x ? 1 : -1);
  // Mitreisender Glow, der in der Bahnmitte am stärksten leuchtet.
  const glow = Math.sin(raw * Math.PI);

  if (cardEl.value) {
    const targetRadius = vanishAtTarget ? 0 : end.borderRadius;
    const targetBorder = vanishAtTarget ? 0 : end.borderWidth;
    const visualRadius = start.borderRadius + (targetRadius - start.borderRadius) * sizeT;
    const visualBorder = hasVisualClone.value
      ? 0
      : start.borderWidth + (targetBorder - start.borderWidth) * sizeT;
    const originShadow = props.origin?.boxShadow && props.origin.boxShadow !== 'none'
      ? `${props.origin.boxShadow}, `
      : '';
    cardEl.value.style.width = `${width.toFixed(2)}px`;
    cardEl.value.style.height = `${height.toFixed(2)}px`;
    cardEl.value.style.transform = makeTransform(x - width / 2, y - height / 2, rotate, lift);
    cardEl.value.style.borderRadius = `${(visualRadius / lift).toFixed(2)}px`;
    cardEl.value.style.borderWidth = `${(visualBorder / lift).toFixed(2)}px`;
    cardEl.value.style.setProperty('--flight-border-width', `${(visualBorder / lift).toFixed(2)}px`);
    cardEl.value.style.setProperty('--flight-border-double', `${(visualBorder * 2 / lift).toFixed(2)}px`);
    // Erst ganz am Ende zusätzlich ausblenden. Primär verschwindet die Karte
    // durch das Schrumpfen; das kurze Fade verhindert einen letzten 1px-Blitz.
    const fadeOut = vanishAtTarget ? Math.max((raw - 0.9) / 0.1, 0) : 0;
    cardEl.value.style.opacity = String(1 - fadeOut);
    cardEl.value.style.boxShadow =
      `${originShadow}0 ${(8 + 22 * glow).toFixed(1)}px ${(18 + 46 * glow).toFixed(1)}px rgba(15, 23, 42, ${(0.28 * glow).toFixed(3)}),` +
      ` 0 0 ${(10 + 38 * glow).toFixed(1)}px color-mix(in srgb, var(--pm-accent, #14b8a6) ${(34 * glow).toFixed(0)}%, transparent)`;
  }
  // Den `contain`-Ausschnitt der Importkachel bis zur Landung beibehalten.
  // Ein früher Wechsel auf das `cover` der Listenansicht würde die Seite noch
  // im Flug sichtbar vergrößern und beschneiden.
  if (sheenEl.value) {
    sheenEl.value.style.opacity = String(Math.min(glow * 0.72, 0.72));
  }

  if (raw < 1) {
    rafId = requestAnimationFrame(step);
  } else {
    finish();
  }
}

let flightStarted = false;
function startFlight() {
  if (flightStarted || done) return;
  if (!props.target) return; // ohne Ziel weiter am Ursprung halten
  flightStarted = true;
  if (cardEl.value) {
    // Auswahlkontur gehört zum Importdialog und löst sich beim Abheben weich.
    cardEl.value.style.outlineColor = 'transparent';
  }
  if (mountedVisualClone) {
    mountedVisualClone.style.outlineColor = 'transparent';
  }
  if (prefersReducedMotion()) {
    // Ohne Bewegung: sofort landen lassen, die Liste übernimmt das Aufleuchten.
    requestAnimationFrame(() => finish());
    return;
  }
  rafId = requestAnimationFrame(step);
}

onMounted(() => {
  const clone = props.origin?.visualClone;
  if (cloneHostEl.value && clone instanceof HTMLElement) {
    mountedVisualClone = clone;
    // Aus dem prozentualen Grid-Layout lösen und exakt in den gemessenen
    // Flugrahmen einspannen. Die inneren Originalelemente und ihre Styles
    // bleiben dabei unverändert erhalten.
    clone.style.position = 'relative';
    clone.style.inset = 'auto';
    clone.style.width = '100%';
    clone.style.height = '100%';
    clone.style.margin = '0';
    clone.style.paddingTop = '0';
    clone.style.boxSizing = 'border-box';
    clone.style.outline = 'none';
    clone.style.pointerEvents = 'none';
    cloneHostEl.value.append(clone);
    const image = clone.matches('img') ? clone : clone.querySelector('img');
    if (image instanceof HTMLImageElement) {
      thumbEl.value = image;
    }
  }
  startFlight(); // fliegt sofort, falls das Ziel schon gesetzt ist
});

// Sobald das Ziel gesetzt wird (nach dem Schließen des Fensters), losfliegen.
watch(() => props.target, () => startFlight());

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId);
});
</script>

<style scoped>
.import-flight-layer {
  position: fixed;
  inset: 0;
  z-index: 3200; /* über Dialog-Overlay */
  pointer-events: none;
}

.import-flight-card {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: center center;
  box-sizing: border-box;
  contain: layout style;
  will-change: transform, width, height, opacity;
  overflow: hidden;
  transition: outline-color 140ms ease;
}

.import-flight-card__thumb {
  position: absolute;
  inset: var(--flight-border-width, 0px);
  width: calc(100% - var(--flight-border-double, 0px));
  height: calc(100% - var(--flight-border-double, 0px));
  display: block;
  transform-origin: center center;
}

.import-flight-card__clone-host {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.import-flight-card__fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--pm-accent, #14b8a6);
  background: var(--pm-surface-muted, #f1f5f9);
}

/* Kurzer Glanz-Streifen, der die Bewegung „materiell" macht. */
.import-flight-card__sheen {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    115deg,
    transparent 40%,
    rgba(255, 255, 255, 0.28) 50%,
    transparent 60%
  );
  mix-blend-mode: screen;
  opacity: 0;
}
</style>
