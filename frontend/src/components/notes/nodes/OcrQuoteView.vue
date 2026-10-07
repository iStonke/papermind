<template>
  <node-view-wrapper
    class="pm-ocrquote"
    :class="{ 'is-selected': selected }"
    contenteditable="false"
  >
    <p class="pm-ocrquote__text">{{ node.attrs.text }}</p>
    <div class="pm-ocrquote__foot">
      <button class="pm-ocrquote__src" type="button" @click="open">
        <span aria-hidden="true">▢</span>
        {{ node.attrs.docTitle }}<template v-if="node.attrs.page"> · S.&nbsp;{{ node.attrs.page }}</template>
        <span v-if="!node.attrs.rects" class="pm-ocrquote__origin">· aus Markierung übernommen</span>
      </button>
      <!-- Lernstoff-Schalter: markiert das Zitat für die Nachbereitung im
           Lernbereich (gleicher Marker wie bei Textzeilen). Der Status
           (offen/Karte/sicher) kommt aus der Lernbereich-Rückkopplung. -->
      <button
        v-if="editor.isEditable || learnKind"
        class="pm-ocrquote__learn"
        :class="[learnKind ? `is-marked is-${learnState}` : '']"
        type="button"
        :disabled="!editor.isEditable"
        :aria-pressed="Boolean(learnKind)"
        :title="learnKind ? 'Nicht mehr als Lernstoff markieren' : 'Als Lernstoff markieren (Nachbereitung im Lernbereich)'"
        @mousedown.prevent
        @click="toggleLearn"
      >
        <v-icon size="13">mdi-school-outline</v-icon>
        <template v-if="learnKind">{{ learnLabel }} · {{ LEARN_STATE_LABELS[learnState] }}</template>
        <template v-else>Zu lernen</template>
      </button>
    </div>
  </node-view-wrapper>
</template>

<script setup>
import { computed } from 'vue';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

const LEARN_STATE_LABELS = { open: 'offen', card: 'Karte', strong: 'sicher' };
// Marker-Typ → kurze Bezeichnung (Farben der Lernmarkierungen: Wichtig →
// lernen, Definition → fakt, Unklar → warum).
const LEARN_KIND_LABELS = { lernen: 'Lernstoff', fakt: 'Definition', warum: 'Offene Frage' };

const learnKind = computed(() => {
  const learn = props.node.attrs.learn;
  return (typeof learn === 'string' ? learn : learn?.kind) || null;
});
const learnLabel = computed(() => LEARN_KIND_LABELS[learnKind.value] || 'Lernstoff');

// Status liefert das learnMarker-Plugin als Node-Dekoration (pm-learn-state--*).
const learnState = computed(() => {
  for (const decoration of props.decorations || []) {
    const state = decoration?.type?.attrs?.['data-learn-state'];
    if (state) return state;
  }
  return 'open';
});

function toggleLearn() {
  if (!props.editor.isEditable || typeof props.getPos !== 'function') return;
  props.editor.commands.toggleLearnMarkerAt(props.getPos(), learnKind.value || 'lernen');
}

function open() {
  // Zuerst der Split-Ansicht anbieten: Zeigt sie dieses Dokument (oder kann es
  // einblenden), springt sie im PDF zur Stelle und verhindert das Event. Sonst
  // wie bisher das Dokument im Dokumentbereich öffnen.
  const reveal = new CustomEvent('pm-note:quote-reveal', {
    cancelable: true,
    detail: { docId: props.node.attrs.docId, page: props.node.attrs.page, rects: props.node.attrs.rects },
  });
  if (!window.dispatchEvent(reveal)) return;
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: {
      type: 'document', id: props.node.attrs.docId,
      label: props.node.attrs.docTitle, page: props.node.attrs.page,
    },
  }));
}
</script>

<style scoped>
.pm-ocrquote {
  border-left: 2.5px solid var(--pm-accent, #006b75);
  background: var(--pm-viewer-surface, #eef2f4);
  border-radius: 0 10px 10px 0;
  padding: 12px 16px;
  margin: 0.7em 0;
}
.pm-ocrquote.is-selected {
  outline: 2px solid rgba(var(--v-theme-primary, 0 107 117), 0.45);
  outline-offset: 2px;
}
.pm-ocrquote__text {
  margin: 0 0 8px;
  font-style: italic;
  color: var(--pm-text, #0e181b);
  line-height: 1.55;
}
.pm-ocrquote__src {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  color: var(--pm-muted, #535e62);
  text-align: left;
}
.pm-ocrquote__src:hover { color: var(--pm-accent-strong, #00555f); }
.pm-ocrquote__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.pm-ocrquote__learn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border: 1px dashed color-mix(in srgb, var(--pm-muted, #535e62) 45%, transparent);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  font: inherit;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.pm-ocrquote__learn:hover:not(:disabled) {
  color: var(--pm-accent-strong, #00555f);
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 55%, transparent);
}
.pm-ocrquote__learn:disabled { cursor: default; }
.pm-ocrquote__learn.is-marked { border-style: solid; }
.pm-ocrquote__learn.is-open {
  color: var(--pm-warning, #b45309);
  border-color: color-mix(in srgb, var(--pm-warning, #b45309) 45%, transparent);
  background: color-mix(in srgb, var(--pm-warning, #b45309) 10%, transparent);
}
.pm-ocrquote__learn.is-card {
  color: var(--pm-accent, #006b75);
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 42%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
}
.pm-ocrquote__learn.is-strong {
  color: var(--pm-success, #307041);
  border-color: color-mix(in srgb, var(--pm-success, #307041) 42%, transparent);
  background: color-mix(in srgb, var(--pm-success, #307041) 11%, transparent);
}
/* Die Lernzeilen-Regeln reservieren rechts Platz für eine Status-Pille – das
   Zitat zeigt seinen Status im eigenen Fuß, braucht den Platz also nicht. */
.pm-ocrquote.pm-ocrquote.pm-learn-state { padding-right: 16px; }
.pm-ocrquote__origin { opacity: 0.8; }
</style>
