<template>
  <div ref="toolbar" class="pm-preview-toolbar" :class="{ 'pm-preview-toolbar--visible': revealed, 'pm-preview-toolbar--expanded': expanded }"
    :style="themeStyle" role="toolbar" :aria-label="label" @focusin="focused = true" @focusout="onFocusOut">
    <slot :touch="touch" />
    <div v-if="showZoom" class="pdf-preview__zoom-controls" role="group" aria-label="Zoom" :inert="expanded">
      <span v-if="$slots.default" class="pm-preview-toolbar__divider pm-preview-toolbar__zoom-divider" aria-hidden="true" />
      <div class="pdf-preview__zoom-stepper">
        <button type="button" tabindex="0" class="pdf-preview__zoom-seg" :disabled="!canZoomOut" aria-label="Verkleinern" @click="emit('zoom-out')"><v-icon size="16">mdi-minus</v-icon></button>
        <button type="button" tabindex="0" class="pdf-preview__zoom-value" :class="{ 'pdf-preview__zoom-value--default': defaultZoom }"
          :aria-label="`Zoom ${zoom} Prozent – ${resetLabel}`" :title="resetLabel" @click="emit('zoom-reset')">{{ zoom }}%</button>
        <button type="button" tabindex="0" class="pdf-preview__zoom-seg" :disabled="!canZoomIn" aria-label="Vergrößern" @click="emit('zoom-in')"><v-icon size="16">mdi-plus</v-icon></button>
      </div>
    </div>
    <slot name="append" :touch="touch" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useTheme } from 'vuetify';

const props = defineProps({
  label: { type: String, default: 'Vorschauwerkzeuge' },
  pinned: Boolean, held: Boolean, expanded: Boolean, showZoom: Boolean,
  zoom: { type: Number, default: 100 }, defaultZoom: Boolean,
  canZoomIn: Boolean, canZoomOut: Boolean,
  resetLabel: { type: String, default: 'Auf 100 % zurücksetzen' },
});
const emit = defineEmits(['zoom-in', 'zoom-out', 'zoom-reset']);
const toolbar = ref(null);
const hovered = ref(false);
const focused = ref(false);
const touch = ref(false);
const revealed = computed(() => props.pinned || props.held || props.expanded || hovered.value || focused.value || touch.value);
const theme = useTheme();
const themeStyle = computed(() => theme.current.value.dark ? {
  '--pdf-toolbar-bg': 'rgb(15 23 42 / .58)', '--pdf-toolbar-border': 'rgb(255 255 255 / .1)',
  '--pdf-toolbar-shadow': '0 8px 22px rgb(0 0 0 / .24)', '--pdf-toolbar-text': 'rgb(226 232 240 / .9)',
  '--pdf-toolbar-text-muted': 'rgb(226 232 240 / .68)', '--pdf-toolbar-icon': 'rgb(226 232 240 / .78)',
  '--pdf-toolbar-hover-bg': 'rgb(255 255 255 / .1)', '--pdf-toolbar-stepper-bg': 'rgb(255 255 255 / .07)',
  '--pdf-toolbar-divider': 'rgb(255 255 255 / .12)',
} : {
  '--pdf-toolbar-bg': 'rgb(255 255 255 / .66)', '--pdf-toolbar-border': 'rgb(203 213 225 / .65)',
  '--pdf-toolbar-shadow': '0 14px 34px rgb(15 23 42 / .12), 0 2px 8px rgb(15 23 42 / .08)',
  '--pdf-toolbar-text': 'rgb(31 41 55 / .88)', '--pdf-toolbar-text-muted': 'rgb(75 85 99 / .72)',
  '--pdf-toolbar-icon': 'rgb(71 85 105 / .76)', '--pdf-toolbar-hover-bg': 'rgb(15 23 42 / .07)',
  '--pdf-toolbar-stepper-bg': 'rgb(241 245 249 / .4)', '--pdf-toolbar-divider': 'rgb(148 163 184 / .24)',
});
let surface;
let media;
function enter(event) { if (event.pointerType !== 'touch') hovered.value = true; }
function leave() { hovered.value = false; }
function updateTouch() { touch.value = Boolean(media?.matches); }
async function onFocusOut() {
  await nextTick();
  focused.value = Boolean(toolbar.value?.contains(document.activeElement));
}
onMounted(() => {
  surface = toolbar.value?.parentElement;
  surface?.addEventListener('pointerenter', enter);
  surface?.addEventListener('pointerleave', leave);
  hovered.value = Boolean(surface?.matches(':hover'));
  media = window.matchMedia('(hover: none), (pointer: coarse)');
  updateTouch();
  media.addEventListener('change', updateTouch);
});
onBeforeUnmount(() => {
  surface?.removeEventListener('pointerenter', enter);
  surface?.removeEventListener('pointerleave', leave);
  media?.removeEventListener('change', updateTouch);
});
</script>

<style scoped>
.pm-preview-toolbar {
  position: absolute; top: 12px; left: 50%; right: auto; transform: translateX(-50%); z-index: 30;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center; width: max-content; min-width: 0;
  max-width: calc(100% - 24px); min-height: 34px; gap: var(--pdf-toolbar-group-gap, 6px); padding: 4px 6px;
  box-sizing: border-box; border: 1px solid var(--pdf-toolbar-border); border-radius: 999px;
  background: var(--pdf-toolbar-bg); box-shadow: var(--pdf-toolbar-shadow); color: var(--pdf-toolbar-text);
  backdrop-filter: blur(6px) saturate(1.08); -webkit-backdrop-filter: blur(6px) saturate(1.08);
  opacity: 0; pointer-events: none; transition: opacity 160ms ease, background 160ms ease;
}
.pm-preview-toolbar--visible, .pm-preview-toolbar:hover, .pm-preview-toolbar:focus-within { opacity: 1; pointer-events: auto; }
.pm-preview-toolbar :deep(.pm-preview-toolbar__divider) { flex: 0 0 1px; width: 1px; height: 16px; margin-inline: var(--pdf-toolbar-divider-margin, 4px); background: var(--pdf-toolbar-divider); }
.pdf-preview__zoom-controls { display: flex; flex: 0 0 auto; align-items: center; max-width: 140px; transition: max-width 180ms ease, opacity 150ms ease; }
.pm-preview-toolbar--expanded .pdf-preview__zoom-controls { max-width: 0; opacity: 0; overflow: hidden; pointer-events: none; }
.pdf-preview__zoom-stepper { display: inline-flex; align-items: center; padding: 1px; border-radius: 999px; background: var(--pdf-toolbar-stepper-bg); }
.pdf-preview__zoom-seg, .pdf-preview__zoom-value { display: inline-flex; align-items: center; justify-content: center; height: 26px; border: 0; border-radius: 999px; background: transparent; cursor: pointer; }
.pdf-preview__zoom-seg { width: 24px; padding: 0; color: var(--pdf-toolbar-icon); }
.pdf-preview__zoom-value { min-width: 40px; padding: 0 2px; color: var(--pdf-toolbar-text); font-size: .78rem; font-variant-numeric: tabular-nums; }
.pdf-preview__zoom-value--default { color: var(--pdf-toolbar-text-muted); }
.pdf-preview__zoom-seg:hover:not(:disabled), .pdf-preview__zoom-value:hover { background: var(--pdf-toolbar-hover-bg); color: var(--pdf-toolbar-text); }
.pdf-preview__zoom-seg:disabled { opacity: .28; cursor: default; }
.pdf-preview__zoom-seg:focus-visible, .pdf-preview__zoom-value:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 1px; }
@media (prefers-reduced-motion: reduce) { .pm-preview-toolbar, .pdf-preview__zoom-controls { transition: none; } }
:global(.pm-no-animations) .pm-preview-toolbar, :global(.pm-no-animations) .pdf-preview__zoom-controls { transition: none; }
</style>
