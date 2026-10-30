<template>
  <div ref="root" class="document-flip" :class="{ 'document-flip--turning': turning, 'document-flip--back': back }">
    <div ref="front" class="document-flip__live" :class="{ 'document-flip__live--hidden': back || turning }"
      :inert="back || turning" :aria-hidden="back || turning">
      <slot />
    </div>
    <div v-show="back || turning" class="document-flip__stage">
      <div ref="card" class="document-flip__card" :style="cardStyle">
        <div ref="paperFace" class="document-flip__face document-flip__paper" :style="{ boxShadow: paperShadow }" aria-hidden="true"><div ref="snapshot" class="document-flip__snapshot" /></div>
        <section ref="backFace" class="document-flip__face document-flip__reverse" :inert="!back || turning"
          :style="{ boxShadow: BACK_SHADOW }" :aria-hidden="!back || turning" aria-label="Zusammenhänge zum Dokument" tabindex="-1">
          <header class="document-flip__heading">
            <h2>Zusammenhänge</h2>
            <p :title="subtitle">{{ subtitle }}</p>
          </header>
          <div ref="backBody" class="document-flip__back-body" :class="{ 'document-flip__back-body--waiting': reservedHeight !== null }"
            :style="reservedHeight !== null ? { height: `${reservedHeight}px` } : undefined" :aria-busy="backSwitching">
            <div :key="documentKey" ref="backContent" class="document-flip__connections" :class="{ 'document-flip__connections--pending': backSwitching }"
              :inert="backSwitching" :aria-hidden="backSwitching">
              <slot v-if="visited" name="back" :active="back" :report-loading="handleBackLoading" />
            </div>
            <div ref="outgoing" class="document-flip__outgoing" aria-hidden="true" inert />
            <span v-if="showBackLoading" class="document-flip__loading" role="status">Zusammenhänge werden geladen …</span>
          </div>
        </section>
        <div class="document-flip__ribbon-face" aria-hidden="true">
          <div class="document-flip__ribbon"><span>Rückseite</span></div>
        </div>
      </div>
    </div>
    <button v-if="enabled && (ready || back || turning)" ref="toggle" type="button" class="document-flip__toggle"
      :aria-label="back ? 'Zurück zum Dokument' : 'Dokument wenden – Zusammenhänge anzeigen'"
      :title="back ? 'Zurück zum Dokument (Esc)' : 'Dokument wenden – Zusammenhänge anzeigen'"
      :aria-pressed="back" @click="turn(!back)">
      <v-icon size="21" aria-hidden="true">{{ back ? 'mdi-file-document-outline' : 'mdi-graph-outline' }}</v-icon>
    </button>
  </div>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
const props = defineProps({ documentKey: [String, Number], title: String, correspondent: String, pageCount: Number, page: { type: Number, default: 1 }, enabled: { type: Boolean, default: true } });
const subtitle = computed(() => {
  const count = Number(props.pageCount);
  const pages = Number.isInteger(count) && count > 0 ? `${count} ${count === 1 ? 'Seite' : 'Seiten'}` : '';
  return [props.title?.trim(), props.correspondent?.trim(), pages].filter(Boolean).join(' · ');
});
const emit = defineEmits(['change', 'lock-change', 'before-turn']);
const root = ref(null), front = ref(null), card = ref(null), snapshot = ref(null), paperFace = ref(null), backFace = ref(null), toggle = ref(null);
const backBody = ref(null), backContent = ref(null), outgoing = ref(null);
const backSwitching = ref(false), reservedHeight = ref(null), showBackLoading = ref(false);
let swapRevision = 0, swapEffects = [], loadingTimer, backLoading = true, revealing = false;
const BACK_SHADOW = '0 14px 48px rgb(0 0 0 / .22)';
const TURN_EASING = 'cubic-bezier(.22, .8, .24, 1)';
const paperShadow = ref('none');
const back = ref(false), turning = ref(false), visited = ref(false), ready = ref(false);
const source = ref({ left: '16px', top: '16px', width: '100px', height: '140px' });
const target = ref({ left: '16px', top: '16px', width: '100px', height: '140px' });
const cardStyle = computed(() => ({ ...(back.value ? target.value : source.value), transform: back.value ? 'rotateY(180deg)' : 'rotateY(0deg)' }));
let mutation, resize, pageResize, observedPage, animation, frame = 0, revision = 0;
let shadowAnimations = [];
let angularVelocity = 0;
function cancelTurn() {
  animation?.cancel(); animation = null;
  shadowAnimations.forEach(effect => effect.cancel());
  shadowAnimations = [];
  angularVelocity = 0;
}
function motionEnabled() { return !root.value?.closest('.pm-no-animations') && !window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
function cancelBackEffects() {
  swapEffects.forEach(effect => effect.cancel());
  swapEffects = [];
  clearTimeout(loadingTimer);
  showBackLoading.value = false;
}
function clearBackChange() {
  swapRevision++;
  cancelBackEffects();
  outgoing.value?.replaceChildren();
  if (outgoing.value) outgoing.value.style.transform = '';
  backSwitching.value = false;
  reservedHeight.value = null;
  revealing = false;
}
function preserveBack() {
  if (!backContent.value || !backBody.value || !outgoing.value) return;
  // Only the outgoing visual is cloned. It is inert, hidden from assistive
  // technology and never used as the new document's interactive content.
  if (!backSwitching.value) {
    const copy = backContent.value.cloneNode(true);
    for (const node of [copy, ...copy.querySelectorAll('*')]) {
      for (const attribute of ['id', 'for', 'aria-labelledby', 'aria-describedby', 'aria-controls']) node.removeAttribute(attribute);
    }
    outgoing.value.replaceChildren(copy);
  }
  swapRevision++;
  cancelBackEffects();
  revealing = false;
  reservedHeight.value = backBody.value.getBoundingClientRect().height;
  backSwitching.value = true;
  backLoading = true;
  loadingTimer = setTimeout(() => { showBackLoading.value = true; }, 240);
}
function handleBackLoading({ documentId, loading }) {
  if (String(documentId) !== String(props.documentKey)) return;
  backLoading = loading;
  if (backSwitching.value && !loading) void revealBack();
}
async function revealBack() {
  if (revealing) return;
  revealing = true;
  const token = swapRevision;
  await nextTick();
  if (token !== swapRevision) return;
  if (backLoading) { revealing = false; return; }
  clearTimeout(loadingTimer);
  showBackLoading.value = false;
  const face = backFace.value;
  const oldScroll = face.scrollTop;
  const top = face.getBoundingClientRect().top;
  const readingTop = top + parseFloat(getComputedStyle(face).paddingTop);
  const oldSections = [...outgoing.value.querySelectorAll('.document-section-card')];
  const index = oldSections.findIndex(section => section.getBoundingClientRect().bottom > readingTop);
  const oldOffset = index < 0 ? 0 : oldSections[index].getBoundingClientRect().top - top;
  reservedHeight.value = null;
  await nextTick();
  if (token !== swapRevision) return;
  // Keep the same section in view when its predecessors have different lengths.
  const section = backContent.value.querySelectorAll('.document-section-card')[index];
  let scroll = oldScroll;
  if (scroll > 0 && section) {
    const offset = Math.max(oldOffset, -section.getBoundingClientRect().height + 40);
    scroll = face.scrollTop + section.getBoundingClientRect().top - face.getBoundingClientRect().top - offset;
  }
  // The temporary outgoing layer can be longer than the new document. Clamp
  // against the live content so removing that layer cannot move the viewport.
  const maxScroll = Math.max(0, backBody.value.offsetTop + backBody.value.offsetHeight
    + parseFloat(getComputedStyle(face).paddingBottom) - face.clientHeight);
  face.scrollTop = Math.min(maxScroll, Math.max(0, scroll));
  outgoing.value.style.transform = `translateY(${face.scrollTop - oldScroll}px)`;
  if (motionEnabled() && back.value) {
    const timing = { duration: 300, easing: 'ease-in-out', fill: 'both' };
    swapEffects = [backContent.value.animate([{ opacity: 0 }, { opacity: 1 }], timing),
      outgoing.value.animate([{ opacity: 1 }, { opacity: 0 }], timing)];
    try { await Promise.all(swapEffects.map(effect => effect.finished)); } catch { return; }
  }
  if (token === swapRevision) clearBackChange();
}
function pageElement() {
  return front.value?.querySelector(`.pdf-preview__page[data-page="${Number(props.page) || 1}"]`)
    || front.value?.querySelector('.pdf-preview__page');
}
function updateReady() {
  ready.value = Boolean(front.value?.querySelector('.pdf-preview--document-ready .pdf-preview__page canvas'))
    && !front.value?.querySelector('.preview-swap[aria-busy="true"]');
  const page = pageElement();
  if (page !== observedPage) {
    pageResize?.disconnect();
    observedPage = page;
    if (page) pageResize?.observe(page);
  }
}
function measureSource() {
  const page = pageElement(), host = root.value;
  if (!page || !host) return;
  const bounds = page.getBoundingClientRect(), stage = host.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  source.value = { left: `${bounds.left - stage.left}px`, top: `${bounds.top - stage.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px` };
}
function retargetTurn() {
  // The front-side layout does not use target geometry. Updating it while
  // the drawer moves would re-render the hidden back on every frame.
  if (!back.value && !turning.value) return;
  measureTarget();
  if (!turning.value || !animation) return;
  // The drawer is moving at the same time. Follow the fitted PDF so the
  // snapshot lands on the real page without a size jump at the handoff.
  if (!back.value) measureSource();
  animation.effect.setKeyframes(turnKeyframes(animation.effect.getKeyframes()[0]));
}
function measureTarget() {
  const host = root.value;
  if (!host) return;
  const width = Math.max(1, Math.min(860, host.clientWidth - 32));
  const height = Math.max(1, host.clientHeight - 32);
  target.value = { left: `${Math.max(0, (host.clientWidth - width) / 2)}px`, top: `${Math.max(0, (host.clientHeight - height) / 2)}px`, width: `${width}px`, height: `${height}px` };
}
function capture() {
  const page = pageElement(), host = root.value, holder = snapshot.value;
  if (!page || !host || !holder) return false;
  const bounds = page.getBoundingClientRect(), stage = host.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return false;
  const copies = [];
  for (const canvas of page.querySelectorAll('canvas')) {
    if (!canvas.width || !canvas.height) continue;
    const rect = canvas.getBoundingClientRect(), copy = document.createElement('canvas');
    if (!rect.width || !rect.height) continue;
    copy.width = canvas.width; copy.height = canvas.height;
    copy.getContext('2d').drawImage(canvas, 0, 0);
    copy.style.cssText = `position:absolute;left:${(rect.left - bounds.left) / bounds.width * 100}%;top:${(rect.top - bounds.top) / bounds.height * 100}%;width:${rect.width / bounds.width * 100}%;height:${rect.height / bounds.height * 100}%;`;
    copies.push(copy);
  }
  if (!copies.length) return false;
  paperShadow.value = getComputedStyle(page).boxShadow;
  holder.replaceChildren(...copies);
  source.value = { left: `${bounds.left - stage.left}px`, top: `${bounds.top - stage.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px` };
  return true;
}
function rotationAngle(transform) {
  const matrix = new DOMMatrixReadOnly(transform);
  let angle = Math.atan2(-matrix.m13, matrix.m11) * 180 / Math.PI;
  // Preserve a small overshoot beyond 180° when reversing direction.
  if (angle < -90) angle += 360;
  return angle;
}
function pose() {
  const style = getComputedStyle(card.value);
  const angle = rotationAngle(style.transform);
  return { ...Object.fromEntries(['left', 'top', 'width', 'height'].map(key => [key, style[key]])), transform: `rotateY(${angle}deg)` };
}
function settling(time) {
  const t = Math.max(0, Math.min(1, (time - .7) / .3));
  // Fade the tiny residual motion to an exact rest, with zero end velocity.
  return { amount: 1 - t ** 3 * (10 - 15 * t + 6 * t * t), slope: -100 * t * t * (1 - t) ** 2 };
}
function angularState(start, end, time) {
  const decay = 7.4, frequency = Math.sqrt(100 - decay * decay);
  const displacement = start - end;
  const momentum = (angularVelocity + decay * displacement) / frequency;
  const cosine = Math.cos(frequency * time), sine = Math.sin(frequency * time), envelope = Math.exp(-decay * time);
  const residual = envelope * (displacement * cosine + momentum * sine);
  const speed = envelope * ((frequency * momentum - decay * displacement) * cosine
    - (frequency * displacement + decay * momentum) * sine);
  const tail = settling(time);
  return { angle: end + residual * tail.amount, velocity: speed * tail.amount + residual * tail.slope };
}
function turnKeyframes(initial) {
  const end = { ...cardStyle.value };
  const startAngle = rotationAngle(initial.transform), endAngle = back.value ? 180 : 0;
  // Sample one continuous damped spring instead of joining a stop and bounce.
  // Position and size settle without overshoot; only the rotation carries inertia.
  return Array.from({ length: 101 }, (_, index) => {
    // Denser samples at the start preserve the brief inherited momentum even
    // when a new turn reverses a sheet that is already near its resting side.
    const time = (index / 100) ** 1.5;
    const progress = 1 - (1 + 10 * time) * Math.exp(-10 * time) * settling(time).amount;
    const geometry = Object.fromEntries(['left', 'top', 'width', 'height'].map(key => {
      const from = parseFloat(initial[key]), to = parseFloat(end[key]);
      return [key, `${from + (to - from) * progress}px`];
    }));
    return { ...geometry, transform: `rotateY(${angularState(startAngle, endAngle, time).angle}deg)`, offset: time, easing: 'linear' };
  });
}
async function turn(value, focus = true) {
  if (value === back.value || (value && (!props.enabled || !ready.value))) return;
  const continuing = turning.value;
  const from = continuing ? pose() : null;
  const momentum = continuing && animation
    ? angularState(rotationAngle(animation.effect.getKeyframes()[0].transform), back.value ? 180 : 0, animation.effect.getComputedTiming().progress || 0).velocity
    : 0;
  const continuingShadow = continuing ? getComputedStyle(paperFace.value).boxShadow : null;
  if (!continuing) emit('before-turn');
  const captured = !continuing && capture();
  if (value && !continuing && !captured) return;
  measureTarget();
  const token = ++revision;
  cancelTurn();
  angularVelocity = momentum;
  back.value = value;
  visited.value = true;
  turning.value = true;
  // Layout follows the requested side immediately; interaction remains locked
  // until the turn finishes, independently of the drawer's slide animation.
  emit('change', value);
  await nextTick();
  if (token !== revision) return;
  const initial = from || { ...(value ? source.value : target.value), transform: value ? 'rotateY(0deg)' : 'rotateY(180deg)' };
  if (motionEnabled() && (continuing || captured)) {
    const timing = { duration: 1000, fill: 'both' };
    animation = card.value.animate(turnKeyframes(initial), timing);
    const fromShadow = continuingShadow || (value ? paperShadow.value : BACK_SHADOW);
    const toShadow = value ? BACK_SHADOW : paperShadow.value;
    // Both faces share the same shadow throughout the turn. The endpoints
    // match the real PDF and the resting back, including a rapid reversal.
    shadowAnimations = [paperFace.value, backFace.value].map(face => face.animate([
      { boxShadow: fromShadow }, { boxShadow: toShadow }
    ], { ...timing, easing: TURN_EASING }));
    try { await Promise.all([animation, ...shadowAnimations].map(effect => effect.finished)); } catch { return; }
  }
  if (token !== revision) return;
  cancelTurn();
  turning.value = false;
  await nextTick();
  if (token !== revision) return;
  if (focus) (value ? backFace.value : toggle.value)?.focus({ preventScroll: true });
  if (!value) { snapshot.value?.replaceChildren(); clearBackChange(); }
}
function reset() {
  revision++;
  cancelTurn();
  clearBackChange();
  const hadFocus = backFace.value?.contains(document.activeElement);
  back.value = false; turning.value = false; visited.value = false;
  emit('change', false);
  snapshot.value?.replaceChildren();
  if (hadFocus) toggle.value?.focus({ preventScroll: true });
  void nextTick(updateReady);
}
function changeDocument(key) {
  if (!key) { reset(); return; }
  if (back.value) preserveBack();
  else clearBackChange();
  revision++;
  cancelTurn();
  const hadFocus = backFace.value?.contains(document.activeElement);
  // Keep the requested side, including a selection made during a turn.
  // The keyed slot starts each document with fresh connection state.
  turning.value = false;
  visited.value = back.value;
  ready.value = false;
  snapshot.value?.replaceChildren();
  emit('change', back.value);
  void nextTick(() => {
    measureTarget(); updateReady();
    if (hadFocus && back.value) backFace.value?.focus({ preventScroll: true });
  });
}
function escape(event) {
  if (event.key !== 'Escape' || !back.value || event.defaultPrevented
    || event.target?.closest?.('[role="dialog"], [role="menu"], [role="listbox"]')) return;
  event.preventDefault(); event.stopImmediatePropagation();
  void turn(false);
}
watch(() => props.documentKey, changeDocument, { flush: 'sync' });
watch(() => props.enabled, enabled => { if (!enabled) reset(); });
watch([back, turning], () => emit('lock-change', back.value || turning.value));
onMounted(() => {
  mutation = new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(updateReady); });
  mutation.observe(front.value, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-busy'] });
  resize = new ResizeObserver(retargetTurn);
  pageResize = new ResizeObserver(() => { if (turning.value && !back.value) retargetTurn(); });
  resize.observe(root.value);
  window.addEventListener('keydown', escape, true);
  updateReady(); measureTarget();
});
onBeforeUnmount(() => {
  clearBackChange();
  revision++; cancelTurn(); mutation?.disconnect(); resize?.disconnect(); pageResize?.disconnect(); cancelAnimationFrame(frame);
  window.removeEventListener('keydown', escape, true);
  emit('change', false);
  emit('lock-change', false);
});
defineExpose({ turn, back });
</script>
<style scoped>
.document-flip { position:relative; display:flex; flex:1; min-width:0; min-height:0; overflow:hidden; isolation:isolate; }
.document-flip__live { display:flex; flex:1; min-width:0; min-height:0; }
.document-flip__live--hidden { visibility:hidden; pointer-events:none; }
.document-flip__stage { position:absolute; inset:0; perspective:1400px; pointer-events:none; }
.document-flip__card { position:absolute; transform-style:preserve-3d; transform-origin:50% 50%; }
.document-flip__face { position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:8px; overflow:hidden; }
.document-flip__paper { background:white; }
.document-flip__snapshot { position:absolute; inset:0; }
.document-flip__reverse { transform:rotateY(180deg); pointer-events:auto; overflow-y:auto; overscroll-behavior:contain; scrollbar-gutter:stable; padding:24px 56px 24px 24px; background:var(--pm-app-surface, #fff); color:var(--pm-text); border:1px solid var(--pm-divider); }
.document-flip__heading { padding-bottom:12px; border-bottom:1px solid var(--pm-divider); }
.document-flip__ribbon-face { position:absolute; inset:0; transform:rotateY(180deg) translateZ(.1px); backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:8px; overflow:hidden; pointer-events:none; }
.document-flip__ribbon { position:absolute; top:0; right:0; width:104px; height:104px; overflow:hidden; }
.document-flip__ribbon span { position:absolute; top:24px; right:-41px; display:flex; align-items:center; justify-content:center; width:160px; height:28px; transform:rotate(45deg); background:#006b75; color:#fff; box-shadow:0 3px 7px rgb(0 0 0 / .2), inset 0 -1px 0 rgb(0 0 0 / .16); font-size:10px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; white-space:nowrap; }
.document-flip__heading h2 { margin:4px 0 2px; font-size:clamp(18px, 2vw, 25px); font-weight:650; letter-spacing:-.02em; }
.document-flip__heading p { margin:0; overflow-wrap:anywhere; color:var(--pm-muted); font-size:12px; line-height:1.5; }
.document-flip__connections { display:grid; gap:14px; }
.document-flip__back-body { position:relative; overflow-anchor:none; }
.document-flip__back-body--waiting { overflow:hidden; }
.document-flip__connections--pending { opacity:0; pointer-events:none; }
.document-flip__outgoing { position:absolute; inset:0 0 auto; pointer-events:none; }
.document-flip__loading { position:absolute; top:24px; right:10px; max-width:calc(100% - 20px); padding:6px 10px; border:1px solid var(--pm-divider); border-radius:100px; background:var(--pm-app-surface, #fff); color:var(--pm-muted); font-size:11px; box-shadow:0 2px 10px rgb(0 0 0 / .08); }
.document-flip__connections :deep(.document-section-card) { margin-top:0; }
.document-flip__connections :deep(.document-section-card:first-child) { margin-top:18px; }
.document-flip__toggle { position:absolute; z-index:5; right:14px; top:50%; transform:translateY(-50%); display:grid; place-items:center; width:38px; height:48px; border:1px solid var(--pm-divider); border-radius:14px; background:color-mix(in srgb, var(--pm-app-surface, #fff) 94%, transparent); color:var(--pm-muted); box-shadow:0 4px 18px rgb(0 0 0 / .15); cursor:pointer; opacity:0; pointer-events:none; transition:opacity 160ms ease, color 160ms ease, box-shadow 160ms ease; }
.document-flip:hover .document-flip__toggle,
.document-flip:has(.pm-preview-toolbar--visible) .document-flip__toggle,
.document-flip__toggle:focus-visible { opacity:1; pointer-events:auto; }
@media (hover:none), (pointer:coarse) { .document-flip__toggle { opacity:1; pointer-events:auto; } }
.document-flip__toggle:hover { color:var(--pm-accent); box-shadow:0 4px 22px color-mix(in srgb, var(--pm-accent) 18%, transparent); }
.document-flip__toggle:focus-visible, .document-flip__reverse:focus-visible { outline:2px solid var(--pm-accent); outline-offset:-3px; }
@media(max-width:600px) { .document-flip__reverse { padding:16px 48px 16px 14px; } .document-flip__toggle { right:9px; width:34px; height:44px; } }
:global(.pm-no-animations .document-flip__toggle) { transition:none; }
@media(prefers-reduced-motion:reduce) { .document-flip__toggle { transition:none; } }
</style>
