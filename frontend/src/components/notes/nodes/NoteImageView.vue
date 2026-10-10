<template>
  <node-view-wrapper
    ref="figureEl"
    as="figure"
    class="pm-note-image"
    :class="{ 'is-selected': selected, 'has-error': loadError }"
    :style="{ '--pm-note-image-width': `${visibleWidth}%` }"
    :data-note-image="''"
    contenteditable="false"
  >
    <div class="pm-note-image__frame" data-drag-handle>
      <img
        v-if="displaySrc"
        :src="displaySrc"
        :alt="imageAlt"
        :title="node.attrs.title || undefined"
        draggable="false"
        :class="{ 'is-expandable': isLectureImage }"
        :role="isLectureImage ? 'button' : undefined"
        :tabindex="isLectureImage ? 0 : undefined"
        :aria-label="isLectureImage ? 'Screenshot vergrößern' : undefined"
        @click.stop="openPreview"
        @pm-lecture-preview="openPreview"
        @keydown.enter.prevent.stop="openPreview"
        @keydown.space.prevent.stop="openPreview"
        @load="loadError = false"
        @error="handleImageError"
      />
      <div v-if="loadError" class="pm-note-image__error" role="status">
        <v-icon size="22">mdi-image-broken-variant</v-icon>
        <span>Bild konnte nicht geladen werden</span>
        <button type="button" @mousedown.prevent.stop @click="retryImage">Erneut versuchen</button>
      </div>

      <div v-if="editor.isEditable && selected && !isLectureImage" class="pm-note-image__tools" role="toolbar" aria-label="Bildgröße">
        <button
          v-for="option in widthOptions"
          :key="option.value"
          type="button"
          :class="{ 'is-active': visibleWidth === option.value }"
          :aria-pressed="visibleWidth === option.value"
          :title="option.label"
          @mousedown.prevent.stop
          @click="setWidth(option.value)"
        >{{ option.short }}</button>
        <span aria-hidden="true"></span>
        <button
          type="button"
          class="is-danger"
          title="Bild entfernen"
          aria-label="Bild entfernen"
          @mousedown.prevent.stop
          @click="deleteNode"
        ><v-icon size="16">mdi-delete-outline</v-icon></button>
      </div>

      <button
        v-if="editor.isEditable && selected && !isLectureImage"
        type="button"
        class="pm-note-image__resize"
        title="Breite ziehen"
        aria-label="Bildbreite durch Ziehen ändern"
        @mousedown.prevent.stop
        @pointerdown.prevent.stop="startResize"
      ></button>
    </div>

    <!-- Folien im Mitschrift-Block: Aufnahmezeit steht in dessen Kopfzeile. -->
    <figcaption v-if="!isLectureImage && (editor.isEditable || caption)" class="pm-note-image__caption">
      <input
        v-if="editor.isEditable"
        type="text"
        :value="caption"
        maxlength="500"
        placeholder="Bildunterschrift hinzufügen …"
        aria-label="Bildunterschrift"
        @mousedown.stop
        @keydown.stop
        @input="updateCaption"
      />
      <span v-else>{{ caption }}</span>
    </figcaption>
    <BaseDialog
      v-model="previewOpen"
      title="Screenshot"
      :header-subtitle="previewSubtitle"
      variant="info"
      width="calc(100vw - 64px)"
      max-width="1100"
      card-class="pm-screenshot-dialog"
      :show-footer="false"
      scrim="black"
    >
      <img class="pm-note-image__preview" :src="displaySrc" :alt="imageAlt" />
    </BaseDialog>
  </node-view-wrapper>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue';
import { useLectureCapture } from './useLectureCapture.js';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

import { authedUrl, getBaseUrl } from '../../../api/client.js';
import { useAuthStore } from '../../../stores/auth.js';
import { normalizeNoteImageWidth } from './noteImageAttrs.js';
import BaseDialog from '../../BaseDialog.vue';

const props = defineProps(nodeViewProps);
const { isLectureImage, captureLabel, slideNumber } = useLectureCapture(props);
const previewSubtitle = computed(() => slideNumber.value
  ? `Folie ${slideNumber.value}${captureLabel.value ? ` · ${captureLabel.value}` : ''}` : '');
const authStore = useAuthStore();
const figureEl = ref(null);
const loadError = ref(false);
const retryVersion = ref(0);
const liveWidth = ref(null);
const previewOpen = ref(false);
function openPreview() {
  if (isLectureImage.value && displaySrc.value && !loadError.value) previewOpen.value = true;
}
let stopResize = null;

const widthOptions = Object.freeze([
  { value: 40, short: 'S', label: 'Klein' },
  { value: 70, short: 'M', label: 'Mittel' },
  { value: 100, short: 'L', label: 'Volle Breite' },
]);

const caption = computed(() => String(props.node.attrs.caption || ''));
const visibleWidth = computed(() => normalizeNoteImageWidth(
  liveWidth.value ?? props.node.attrs.displayWidth,
));
const imageAlt = computed(() => String(
  props.node.attrs.alt || caption.value || props.node.attrs.title || '',
));

function absoluteAssetUrl(src) {
  const value = String(src || '').trim();
  if (!value) return '';
  // Only PaperMind-owned note image routes are rendered. This also guarantees
  // that a short-lived file token can never be attached to a third-party URL.
  if (!/^\/api\/notes\/[0-9a-f-]+\/images\/[0-9a-f-]+\/file$/i.test(value)) return '';
  const base = String(getBaseUrl() || '').replace(/\/$/, '');
  return `${base}${value.startsWith('/') ? value : `/${value}`}`;
}

const displaySrc = computed(() => {
  // Recompute once the initial token arrives and after a targeted retry. Token
  // rotation alone does not reload already successful images.
  void authStore.hasFileToken;
  const version = retryVersion.value;
  const assetUrl = absoluteAssetUrl(props.node.attrs.src);
  if (!assetUrl) return '';
  const url = authedUrl(assetUrl);
  if (!url || !version) return url;
  return `${url}${url.includes('?') ? '&' : '?'}image_retry=${version}`;
});

function setWidth(value) {
  liveWidth.value = null;
  props.updateAttributes({ displayWidth: normalizeNoteImageWidth(value) });
}

function updateCaption(event) {
  const value = String(event.target.value || '').slice(0, 500);
  props.updateAttributes({
    caption: value,
    alt: value || props.node.attrs.title || '',
  });
}

async function retryImage() {
  await authStore.refreshFileToken();
  loadError.value = false;
  retryVersion.value += 1;
}

function handleImageError() {
  loadError.value = true;
}

function startResize(event) {
  if (stopResize) stopResize();
  const wrapper = figureEl.value?.$el || figureEl.value;
  const container = wrapper?.parentElement;
  const containerWidth = container?.getBoundingClientRect().width || 0;
  if (!containerWidth) return;
  const startX = event.clientX;
  const startWidth = visibleWidth.value;

  const move = (moveEvent) => {
    const deltaPercent = ((moveEvent.clientX - startX) * 2 / containerWidth) * 100;
    liveWidth.value = normalizeNoteImageWidth(startWidth + deltaPercent);
  };
  const end = (commit = true) => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', end);
    window.removeEventListener('pointercancel', end);
    const committed = visibleWidth.value;
    liveWidth.value = null;
    if (commit) props.updateAttributes({ displayWidth: committed });
    stopResize = null;
  };
  stopResize = end;
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', end, { once: true });
  window.addEventListener('pointercancel', end, { once: true });
}

onBeforeUnmount(() => stopResize?.(false));
</script>

<style scoped>
.pm-note-image {
  position: relative;
  width: var(--pm-note-image-width, 100%);
  max-width: 100%;
  margin: 1.15em auto;
  transition: width 120ms ease;
}

.pm-note-image__frame {
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 84%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--pm-surface-soft, #f3f7f7) 82%, #fff);
  line-height: 0;
}

.pm-note-image.is-selected .pm-note-image__frame {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 66%, var(--pm-divider, #d8dfe1));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 16%, transparent);
}

.pm-note-image img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 72vh;
  object-fit: contain;
}

.pm-note-image img.is-expandable { cursor: zoom-in; }
.pm-note-image img.is-expandable:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: -3px; }
.pm-note-image__preview {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: contain;
  margin: auto;
}

.pm-note-image__tools {
  position: absolute;
  top: 9px;
  right: 9px;
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 85%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 94%, transparent);
  box-shadow: 0 3px 14px rgba(16, 38, 42, 0.12);
  line-height: 1;
}

.pm-note-image__tools button {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pm-muted, #59666a);
  font: 700 0.68rem/1 ui-monospace, monospace;
  cursor: pointer;
}

.pm-note-image__tools button:hover,
.pm-note-image__tools button.is-active {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.pm-note-image__tools > span {
  width: 1px;
  height: 18px;
  margin: 0 2px;
  background: var(--pm-divider, #d8dfe1);
}

.pm-note-image__tools button.is-danger:hover {
  background: color-mix(in srgb, #b93e3e 12%, transparent);
  color: #a12f2f;
}

.pm-note-image__resize {
  position: absolute;
  right: 5px;
  bottom: 5px;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 90%, transparent);
  cursor: nwse-resize;
}

.pm-note-image__resize::after {
  content: '';
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 7px;
  height: 7px;
  border-right: 2px solid var(--pm-accent-strong, #00555f);
  border-bottom: 2px solid var(--pm-accent-strong, #00555f);
}

.pm-note-image__caption {
  display: block;
  margin-top: 7px;
  color: var(--pm-muted, #667377);
  font-size: 0.82rem;
  line-height: 1.35;
  text-align: center;
}

.pm-note-image__caption input {
  width: min(100%, 560px);
  padding: 2px 6px;
  border: 0;
  border-bottom: 1px solid transparent;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: center;
}

.pm-note-image__caption input:focus {
  border-bottom-color: color-mix(in srgb, var(--pm-accent, #006b75) 38%, transparent);
}

.pm-note-image__caption input::placeholder { color: color-mix(in srgb, currentColor 58%, transparent); }

.pm-note-image__error {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--pm-muted, #667377);
  font-size: 0.86rem;
  line-height: 1.3;
}

.pm-note-image__error button {
  padding: 5px 8px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 6px;
  background: var(--pm-content-surface, #fff);
  color: var(--pm-accent-strong, #00555f);
  cursor: pointer;
}

@media (prefers-reduced-motion: reduce) {
  .pm-note-image { transition: none; }
}
</style>

<style>
.pm-dialog.pm-screenshot-dialog {
  display: flex;
  flex-direction: column;
  height: min(82dvh, 820px) !important;
  flex: 0 0 auto !important;
  max-height: calc(100dvh - 48px);
  overflow: hidden;
}
.pm-screenshot-dialog .pm-dialog__header { flex: 0 0 auto; }
.pm-screenshot-dialog .pm-dialog__content-wrap {
  display: flex;
  flex: 1 1 0;
  min-height: 0;
  max-height: none;
  overflow: hidden;
}
.pm-screenshot-dialog .pm-dialog__content {
  position: relative;
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.pm-screenshot-dialog .pm-note-image__preview {
  position: absolute;
  inset: 16px;
  width: calc(100% - 32px) !important;
  height: calc(100% - 32px) !important;
  max-height: none !important;
}
</style>
