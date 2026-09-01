<template>
  <node-view-wrapper
    as="section"
    class="pm-template"
    :class="[`is-${variant}`, { 'is-selected': selected, 'is-arriving': isArriving }]"
    :style="{ '--pm-tpl-color': colorHex }"
    :data-template-box="''"
    :data-variant="variant"
    :data-color="colorKey"
  >
    <header class="pm-template__head" contenteditable="false">
      <span class="pm-template__glyph" aria-hidden="true">▤</span>
      <input
        v-if="editor.isEditable"
        class="pm-template__title"
        type="text"
        :value="title"
        placeholder="Vorlage"
        aria-label="Titel der Vorlage"
        spellcheck="false"
        @mousedown.stop
        @keydown.stop
        @input="onTitleInput"
      />
      <span v-else class="pm-template__title pm-template__title--readonly">{{ title || 'Vorlage' }}</span>

      <div v-if="editor.isEditable" class="pm-template__tools">
        <div class="pm-template__swatches" role="group" aria-label="Farbe wählen">
          <button
            v-for="option in colors"
            :key="option.key"
            type="button"
            class="pm-template__swatch"
            :class="{ 'is-active': option.key === colorKey }"
            :style="{ '--sw': option.hex }"
            :title="option.label"
            :aria-label="`Farbe ${option.label}`"
            :aria-pressed="option.key === colorKey"
            @mousedown.prevent.stop
            @click="setColor(option.key)"
          ></button>
        </div>
        <button
          v-if="canSaveAsTemplate"
          type="button"
          class="pm-template__save"
          aria-label="Als Schnellblock speichern"
          title="Als Schnellblock speichern"
          @mousedown.prevent.stop
          @click="saveAsTemplate"
        >
          <v-icon size="16">mdi-content-save-outline</v-icon>
        </button>
      </div>
    </header>

    <node-view-content class="pm-template__fields" />
  </node-view-wrapper>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';
import {
  NOTE_TEMPLATE_COLORS,
  normalizeTemplateColor,
  normalizeTemplateVariant,
  templateColorHex,
} from './noteTemplates.js';

const props = defineProps(nodeViewProps);

const variant = computed(() => normalizeTemplateVariant(props.node.attrs.variant));
const title = computed(() => props.node.attrs.title || '');
const colors = NOTE_TEMPLATE_COLORS;
const colorKey = computed(() => normalizeTemplateColor(props.node.attrs.color));
const colorHex = computed(() => templateColorHex(colorKey.value));

function setColor(key) {
  props.updateAttributes({ color: normalizeTemplateColor(key) });
}

const canSaveAsTemplate = computed(() => typeof props.extension?.options?.onSaveAsTemplate === 'function');

// Aktuellen Box-Zustand (Titel, Farbe, Feldzeilen) als Baustein-Vorlage abgeben.
function saveAsTemplate() {
  const handler = props.extension?.options?.onSaveAsTemplate;
  if (typeof handler !== 'function') return;
  const fields = [];
  props.node.forEach((child) => {
    if (child.type.name === 'templateField') {
      fields.push({ label: child.attrs.label || '', hint: child.attrs.hint || '' });
    }
  });
  handler({ title: title.value, color: colorKey.value, fields });
}

const insertedAt = Date.parse(props.node.attrs.insertedAt || '');
const isArriving = ref(
  props.editor.isEditable
  && Number.isFinite(insertedAt)
  && Math.abs(Date.now() - insertedAt) <= 4000,
);
let arrivalTimer = null;

onMounted(() => {
  if (!isArriving.value) return;
  arrivalTimer = window.setTimeout(() => {
    isArriving.value = false;
    arrivalTimer = null;
  }, 760);
});

onBeforeUnmount(() => {
  if (arrivalTimer) window.clearTimeout(arrivalTimer);
});

function onTitleInput(event) {
  props.updateAttributes({ title: event.target.value });
}
</script>

<style scoped>
.pm-template {
  --pm-tpl-color: var(--pm-accent, #006b75);
  --pm-tf-label-w: 104px;
  position: relative;
  margin: 0.9em 0;
  padding: 11px 16px 13px;
  border: 1px solid color-mix(in srgb, var(--pm-tpl-color) 32%, var(--pm-divider, #d8dfe1));
  border-radius: 0 10px 10px 0;
  background: color-mix(in srgb, var(--pm-tpl-color) 7%, var(--pm-content-surface, #fff));
}

.pm-template::before {
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 3px;
  border-radius: 10px 0 0 10px;
  background: var(--pm-tpl-color);
  pointer-events: none;
  transform-origin: top;
}

.pm-template.is-selected {
  outline: 2px solid color-mix(in srgb, var(--pm-tpl-color) 42%, transparent);
  outline-offset: 2px;
}

.pm-template__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 9px;
  color: var(--pm-tpl-color);
}

.pm-template__glyph {
  display: inline-grid;
  width: 20px;
  height: 20px;
  flex: none;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--pm-tpl-color) 42%, transparent);
  border-radius: 5px;
  font-size: 12px;
}

.pm-template__title {
  flex: 1 1 auto;
  min-width: 0;
  padding: 2px 0;
  border: 0;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.pm-template__title::placeholder {
  color: currentColor;
  opacity: 0.5;
}

.pm-template__title--readonly { cursor: default; }

/* Kopf-Toolbar: erscheint bei Hover/Fokus des Blocks. Reserviert keinen Platz,
   damit lange Titel nicht dauerhaft eingeengt werden — kleiner Versatz beim
   Einblenden ist akzeptabel. */
.pm-template__tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding-left: 8px;
  opacity: 0;
  transform: translateY(-1px);
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease;
}

.pm-template:hover .pm-template__tools,
.pm-template:focus-within .pm-template__tools,
.pm-template.is-selected .pm-template__tools {
  opacity: 1;
  transform: none;
  pointer-events: auto;
}

.pm-template__swatches {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pm-template__swatch {
  width: 14px;
  height: 14px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--sw) 55%, transparent);
  border-radius: 50%;
  background: var(--sw);
  cursor: pointer;
  transition: transform 100ms ease, box-shadow 100ms ease;
}

.pm-template__swatch:hover { transform: scale(1.15); }

.pm-template__swatch.is-active {
  box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 3px var(--sw);
}

.pm-template__save {
  display: grid;
  width: 28px;
  height: 28px;
  flex: none;
  place-items: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--pm-tpl-color) 34%, var(--pm-divider, #d8dfe1));
  border-radius: 7px;
  background: transparent;
  color: var(--pm-tpl-color);
  cursor: pointer;
  transition: background 120ms ease;
}

.pm-template__save:hover {
  background: color-mix(in srgb, var(--pm-tpl-color) 12%, transparent);
}

.pm-template__fields {
  display: block;
}

/* Ankunfts-Animation (wie beim Callout) */
.pm-template.is-arriving::before {
  animation: pm-template-line-grow 340ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
.pm-template.is-arriving .pm-template__glyph {
  animation: pm-template-glyph-arrive 280ms cubic-bezier(0.16, 1, 0.3, 1) 105ms both;
}
.pm-template.is-arriving .pm-template__fields {
  animation: pm-template-content-arrive 320ms ease-out 165ms both;
}

@keyframes pm-template-line-grow {
  from { opacity: 0.35; transform: scaleY(0); }
  to { opacity: 1; transform: scaleY(1); }
}
@keyframes pm-template-glyph-arrive {
  from { opacity: 0; transform: translateY(3px) scale(0.72); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes pm-template-content-arrive {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .pm-template.is-arriving::before,
  .pm-template.is-arriving .pm-template__glyph,
  .pm-template.is-arriving .pm-template__fields { animation: none; }
}

:global(.pm-no-animations) .pm-template.is-arriving::before,
:global(.pm-no-animations) .pm-template.is-arriving .pm-template__glyph,
:global(.pm-no-animations) .pm-template.is-arriving .pm-template__fields {
  animation: none;
}
</style>
