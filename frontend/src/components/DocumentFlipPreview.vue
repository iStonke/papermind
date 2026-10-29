<template>
  <div ref="root" class="document-flip" :class="{ 'document-flip--turning': turning, 'document-flip--back': back }">
    <div ref="front" class="document-flip__live" :class="{ 'document-flip__live--hidden': back || turning }"
      :inert="back || turning" :aria-hidden="back || turning">
      <slot />
    </div>
    <div v-show="back || turning" class="document-flip__stage">
      <div ref="card" class="document-flip__card" :style="cardStyle">
        <div class="document-flip__face document-flip__paper" aria-hidden="true"><div ref="snapshot" class="document-flip__snapshot" /></div>
        <section ref="backFace" class="document-flip__face document-flip__reverse" :inert="!back || turning"
          :aria-hidden="!back || turning" aria-label="Zusammenhänge zum Dokument" tabindex="-1">
          <header class="document-flip__heading">
            <h2>Zusammenhänge</h2>
            <p :title="title">{{ title }}</p>
          </header>
          <div :key="documentKey" class="document-flip__connections"><slot v-if="visited" name="back" :active="back" /></div>
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
      <v-icon size="21" aria-hidden="true">mdi-flip-horizontal</v-icon>
    </button>
  </div>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
const props = defineProps({ documentKey: [String, Number], title: String, page: { type: Number, default: 1 }, enabled: { type: Boolean, default: true } });
const emit = defineEmits(['change', 'lock-change', 'before-turn']);
const root = ref(null), front = ref(null), card = ref(null), snapshot = ref(null), backFace = ref(null), toggle = ref(null);
const back = ref(false), turning = ref(false), visited = ref(false), ready = ref(false);
const source = ref({ left: '16px', top: '16px', width: '100px', height: '140px' });
const target = ref({ left: '16px', top: '16px', width: '100px', height: '140px' });
const cardStyle = computed(() => ({ ...(back.value ? target.value : source.value), transform: back.value ? 'rotateY(180deg)' : 'rotateY(0deg)' }));
let mutation, resize, animation, frame = 0, revision = 0;
function motionEnabled() { return !root.value?.closest('.pm-no-animations') && !window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
function pageElement() {
  return front.value?.querySelector(`.pdf-preview__page[data-page="${Number(props.page) || 1}"]`)
    || front.value?.querySelector('.pdf-preview__page');
}
function updateReady() {
  ready.value = Boolean(front.value?.querySelector('.pdf-preview--document-ready .pdf-preview__page canvas'))
    && !front.value?.querySelector('.preview-swap[aria-busy="true"]');
}
function measureTarget() {
  const host = root.value;
  if (!host) return;
  const width = Math.max(1, Math.min(860, host.clientWidth - 32));
  target.value = { left: `${Math.max(0, (host.clientWidth - width) / 2)}px`, top: '16px', width: `${width}px`, height: `${Math.max(1, host.clientHeight - 32)}px` };
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
  holder.replaceChildren(...copies);
  source.value = { left: `${bounds.left - stage.left}px`, top: `${bounds.top - stage.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px` };
  return true;
}
function pose() {
  const style = getComputedStyle(card.value);
  return Object.fromEntries(['left', 'top', 'width', 'height', 'transform'].map(key => [key, style[key]]));
}
async function turn(value, focus = true) {
  if (value === back.value || (value && (!props.enabled || !ready.value))) return;
  const continuing = turning.value;
  const from = continuing ? pose() : null;
  if (!continuing) emit('before-turn');
  const captured = !continuing && capture();
  if (value && !continuing && !captured) return;
  measureTarget();
  const token = ++revision;
  animation?.cancel();
  animation = null;
  back.value = value;
  visited.value = true;
  turning.value = true;
  await nextTick();
  if (token !== revision) return;
  const initial = from || { ...(value ? source.value : target.value), transform: value ? 'rotateY(0deg)' : 'rotateY(180deg)' };
  if (motionEnabled() && (continuing || captured)) {
    animation = card.value.animate([initial, { ...cardStyle.value }], { duration: 720, easing: 'cubic-bezier(.22, .8, .24, 1)', fill: 'both' });
    try { await animation.finished; } catch { return; }
  }
  if (token !== revision) return;
  animation?.cancel(); animation = null;
  turning.value = false;
  emit('change', value);
  await nextTick();
  if (token !== revision) return;
  if (focus) (value ? backFace.value : toggle.value)?.focus({ preventScroll: true });
  if (!value) snapshot.value?.replaceChildren();
}
function reset() {
  revision++;
  animation?.cancel(); animation = null;
  const hadFocus = backFace.value?.contains(document.activeElement);
  back.value = false; turning.value = false; visited.value = false;
  emit('change', false);
  snapshot.value?.replaceChildren();
  if (hadFocus) toggle.value?.focus({ preventScroll: true });
  void nextTick(updateReady);
}
function changeDocument(key) {
  if (!key) { reset(); return; }
  revision++;
  animation?.cancel(); animation = null;
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
    if (backFace.value) backFace.value.scrollTop = 0;
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
  resize = new ResizeObserver(() => {
    measureTarget();
    // Keep the turn continuous when the details panel or window changes size.
    if (turning.value && animation) {
      animation.effect.setKeyframes([animation.effect.getKeyframes()[0], { ...cardStyle.value }]);
    }
  });
  resize.observe(root.value);
  window.addEventListener('keydown', escape, true);
  updateReady(); measureTarget();
});
onBeforeUnmount(() => {
  revision++; animation?.cancel(); mutation?.disconnect(); resize?.disconnect(); cancelAnimationFrame(frame);
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
.document-flip__face { position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:8px; overflow:hidden; box-shadow:0 14px 48px rgb(0 0 0 / .22); }
.document-flip__paper { background:white; }
.document-flip__snapshot { position:absolute; inset:0; }
.document-flip__reverse { transform:rotateY(180deg); pointer-events:auto; overflow-y:auto; overscroll-behavior:contain; scrollbar-gutter:stable; padding:24px 56px 24px 24px; background:var(--pm-app-surface, #fff); color:var(--pm-text); border:1px solid var(--pm-divider); }
.document-flip__heading { padding-bottom:12px; border-bottom:1px solid var(--pm-divider); }
.document-flip__ribbon-face { position:absolute; inset:0; transform:rotateY(180deg) translateZ(.1px); backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:8px; overflow:hidden; pointer-events:none; }
.document-flip__ribbon { position:absolute; top:0; right:0; width:104px; height:104px; overflow:hidden; }
.document-flip__ribbon span { position:absolute; top:24px; right:-41px; display:flex; align-items:center; justify-content:center; width:160px; height:28px; transform:rotate(45deg); background:#006b75; color:#fff; box-shadow:0 3px 7px rgb(0 0 0 / .2), inset 0 -1px 0 rgb(0 0 0 / .16); font-size:10px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; white-space:nowrap; }
.document-flip__heading h2 { margin:4px 0 6px; font-size:clamp(18px, 2vw, 25px); font-weight:650; letter-spacing:-.02em; }
.document-flip__heading p { margin:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--pm-muted); font-size:12px; }
.document-flip__connections { display:grid; gap:14px; }
.document-flip__connections :deep(.document-section-card) { margin-top:0; }
.document-flip__connections :deep(.document-section-card:first-child) { margin-top:18px; }
.document-flip__toggle { position:absolute; z-index:5; right:14px; top:50%; transform:translateY(-50%); display:grid; place-items:center; width:38px; height:48px; border:1px solid var(--pm-divider); border-radius:14px; background:color-mix(in srgb, var(--pm-app-surface, #fff) 94%, transparent); color:var(--pm-muted); box-shadow:0 4px 18px rgb(0 0 0 / .15); cursor:pointer; transition:color 160ms ease, box-shadow 160ms ease; }
.document-flip__toggle:hover { color:var(--pm-accent); box-shadow:0 4px 22px color-mix(in srgb, var(--pm-accent) 18%, transparent); }
.document-flip__toggle:focus-visible, .document-flip__reverse:focus-visible { outline:2px solid var(--pm-accent); outline-offset:-3px; }
@media(max-width:600px) { .document-flip__reverse { padding:16px 48px 16px 14px; } .document-flip__toggle { right:9px; width:34px; height:44px; } }
:global(.pm-no-animations .document-flip__toggle) { transition:none; }
@media(prefers-reduced-motion:reduce) { .document-flip__toggle { transition:none; } }
</style>
