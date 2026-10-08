<template>
  <node-view-wrapper
    class="pm-ocrquote"
    contenteditable="false"
  >
    <p
      class="pm-ocrquote__text"
      tabindex="0"
      @pointerdown.stop
      @mousedown.stop="focusQuoteText"
      @mouseup.stop
      @click.stop
      @keydown.stop
      @copy.stop="copyQuoteSelection"
    >{{ node.attrs.text }}</p>
    <div class="pm-ocrquote__foot">
      <button class="pm-ocrquote__src" type="button" @click="open">
        <span aria-hidden="true">▢</span>
        <span class="pm-ocrquote__source-label">
          {{ node.attrs.docTitle }}<template v-if="node.attrs.page"> · S.&nbsp;{{ node.attrs.page }}</template>
          <span v-if="!node.attrs.rects" class="pm-ocrquote__origin">· aus Markierung übernommen</span>
        </span>
      </button>
      <!-- Lernstoff vormerken; Aufbereitung und Fortschritt liegen im Lernraum. -->
      <button
        v-if="editor.isEditable || learnKind"
        class="pm-ocrquote__learn"
        :class="{ 'is-marked': Boolean(learnKind) }"
        type="button"
        :disabled="!editor.isEditable"
        :aria-pressed="Boolean(learnKind)"
        :title="learnKind ? 'Nicht mehr als Lernstoff markieren' : 'Als Lernstoff markieren (Nachbereitung im Lernbereich)'"
        @mousedown.prevent
        @click="toggleLearn"
      >
        <v-icon size="13">mdi-school-outline</v-icon>
        <template v-if="learnKind">Lernstoff</template>
        <template v-else>+ Lernstoff</template>
      </button>
      <button
        v-if="editor.isEditable"
        type="button"
        class="pm-ocrquote__remove"
        title="Box und Markierung entfernen"
        aria-label="Box und Markierung entfernen"
        :disabled="removing"
        @mousedown.prevent
        @click="removeQuote"
      >
        <v-icon size="15">mdi-trash-can-outline</v-icon>
      </button>
    </div>
    <div v-if="editor.isEditable || node.attrs.ownNote" class="pm-ocrquote__annotation">
      <button
        type="button"
        class="pm-ocrquote__annotation-toggle"
        :aria-expanded="noteExpanded"
        :aria-label="node.attrs.ownNote ? 'Eigene Notiz' : 'Eigene Notiz hinzufügen'"
        @click="toggleOwnNote"
      >
        <v-icon size="15" class="pm-ocrquote__annotation-chevron" :class="{ 'is-expanded': noteExpanded }">mdi-chevron-right</v-icon>
        <span>{{ node.attrs.ownNote ? 'Eigene Notiz' : 'Eigene Notiz hinzufügen' }}</span>
        <span v-if="!noteExpanded && node.attrs.ownNote" class="pm-ocrquote__annotation-preview">{{ node.attrs.ownNote }}</span>
      </button>
      <Transition :css="false" @enter="expandOwnNote" @leave="collapseOwnNote" @enter-cancelled="cancelNoteAnimation" @leave-cancelled="cancelNoteAnimation">
        <div v-if="noteExpanded" class="pm-ocrquote__annotation-body">
          <textarea
        ref="ownNoteInput"
        class="pm-ocrquote__annotation-input"
        aria-label="Eigene Notiz"
        placeholder="Eigene Gedanken, Beispiele oder Fragen …"
        rows="1"
        :value="node.attrs.ownNote || ''"
        :readonly="!editor.isEditable"
        @input="updateOwnNote"
          />
        </div>
      </Transition>
    </div>
  </node-view-wrapper>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);
const noteExpanded = ref(false);
const ownNoteInput = ref(null);
const noteAnimations = new WeakMap();
function animateOwnNote(element, opening, done) {
  cancelNoteAnimation(element);
  // Measure the full textarea before choosing the animation's target height.
  resizeOwnNote(element.querySelector('textarea'));
  element.style.overflow = 'hidden';
  const height = element.scrollHeight;
  const animation = element.animate([
    { height: `${opening ? 0 : height}px` },
    { height: `${opening ? height : 0}px` },
  ], {
    duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 220,
    easing: 'ease-in-out',
  });
  noteAnimations.set(element, animation);
  animation.onfinish = () => {
    noteAnimations.delete(element);
    element.style.overflow = '';
    done();
  };
}
function expandOwnNote(element, done) { animateOwnNote(element, true, done); }
function collapseOwnNote(element, done) { animateOwnNote(element, false, done); }
function cancelNoteAnimation(element) {
  noteAnimations.get(element)?.cancel();
  noteAnimations.delete(element);
  element.style.overflow = '';
}
function resizeOwnNote(input = ownNoteInput.value) {
  if (!input) return;
  input.style.height = 'auto';
  input.style.height = `${input.scrollHeight}px`;
}
watch(ownNoteInput, (input, previous, onCleanup) => {
  if (!input) return;
  resizeOwnNote(input);
  let width = input.getBoundingClientRect().width;
  const observer = new ResizeObserver(() => {
    const nextWidth = input.getBoundingClientRect().width;
    if (nextWidth !== width) {
      width = nextWidth;
      resizeOwnNote(input);
    }
  });
  observer.observe(input);
  onCleanup(() => observer.disconnect());
}, { flush: 'post' });
watch(() => props.node.attrs.ownNote, () => resizeOwnNote(), { flush: 'post' });
async function toggleOwnNote() {
  noteExpanded.value = !noteExpanded.value;
  if (noteExpanded.value) {
    await nextTick();
    ownNoteInput.value?.focus({ preventScroll: true });
  }
}
function updateOwnNote(event) {
  resizeOwnNote(event.target);
  if (props.editor.isEditable) props.updateAttributes({ ownNote: event.target.value });
}

const learnKind = computed(() => {
  const learn = props.node.attrs.learn;
  return (typeof learn === 'string' ? learn : learn?.kind) || null;
});
const removing = ref(false);
function removeQuote(event) {
  if (removing.value || !props.editor.isEditable) return;
  removing.value = true;
  const request = new CustomEvent('pm-note-quote-remove', {
    bubbles: true,
    cancelable: true,
    detail: {
      attrs: { ...props.node.attrs },
      remove: () => props.deleteNode(),
      finish: () => { removing.value = false; },
    },
  });
  // Der Workspace entfernt zuerst eine eventuell gespeicherte PDF-Markierung.
  if (event.currentTarget.dispatchEvent(request)) {
    props.deleteNode();
    removing.value = false;
  }
}

function focusQuoteText(event) {
  event.currentTarget.focus({ preventScroll: true });
}

function copyQuoteSelection(event) {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !event.clipboardData) return;
  const text = event.currentTarget;
  if (!text.contains(selection.anchorNode) || !text.contains(selection.focusNode)) return;
  event.clipboardData.setData('text/plain', selection.toString());
  event.preventDefault();
}

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

.pm-ocrquote__text {
  cursor: text;
  user-select: text;
  -webkit-user-select: text;
  margin: 0 0 8px;
  font-style: italic;
  color: var(--pm-text, #0e181b);
  line-height: 1.55;
}
.pm-ocrquote__text:focus { outline: none; }
.pm-ocrquote__annotation {
  margin: 12px -16px -12px;
  padding: 10px 16px 12px;
  border-top: 1px solid color-mix(in srgb, var(--pm-muted, #535e62) 12%, transparent);
  border-radius: 0 0 10px 0;
  background: color-mix(in srgb, var(--pm-viewer-surface, #eef2f4) 65%, var(--pm-content-surface, #fff));
}
.pm-ocrquote__annotation-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  width: 100%;
  min-width: 0;
  padding: 3px 0;
  border: 0;
  background: transparent;
  color: var(--pm-muted, #535e62);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  cursor: pointer;
}
.pm-ocrquote__annotation-toggle > span:not(.pm-ocrquote__annotation-preview) { flex: none; }
.pm-ocrquote__annotation-chevron {
  flex: none;
  transition: transform 180ms ease;
}
.pm-ocrquote__annotation-chevron.is-expanded { transform: rotate(90deg); }
.pm-ocrquote__annotation-body { display: flow-root; }
@media (prefers-reduced-motion: reduce) {
  .pm-ocrquote__annotation-chevron { transition: none; }
}
.pm-ocrquote__annotation-preview { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; opacity: 0.75; }
.pm-ocrquote__annotation-toggle:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 3px; }
.pm-ocrquote__annotation-input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-top: 8px;
  padding: 4px 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.85rem;
  line-height: 1.5;
  resize: none;
  overflow: hidden;
  user-select: text;
  -webkit-user-select: text;
}
.pm-ocrquote__annotation-input:focus { outline: none; }
.pm-ocrquote__annotation-input::placeholder { color: var(--pm-muted, #535e62); opacity: 0.7; }

.pm-ocrquote__src {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  flex: 1 1 180px;
  min-width: 0;
  gap: 5px;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  color: var(--pm-muted, #535e62);
  text-align: left;
}
.pm-ocrquote__source-label { min-width: 0; overflow-wrap: anywhere; }
.pm-ocrquote__src > span:first-child { flex: none; }
.pm-ocrquote__src:focus-visible,
.pm-ocrquote__learn:focus-visible {
  outline: 2px solid var(--pm-accent, #006b75);
  outline-offset: 3px;
}
.pm-ocrquote__src:hover { color: var(--pm-accent-strong, #00555f); }
.pm-ocrquote__foot {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid color-mix(in srgb, var(--pm-muted, #535e62) 16%, transparent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.pm-ocrquote__learn {
  flex: none;
  margin-left: auto;
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
.pm-ocrquote__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted, #64748b);
  cursor: pointer;
}
.pm-ocrquote__remove:hover:not(:disabled) { background: color-mix(in srgb, var(--pm-muted, #64748b) 10%, transparent); }
.pm-ocrquote__remove:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
.pm-ocrquote__remove:disabled { opacity: 0.5; cursor: wait; }
.pm-ocrquote__learn.is-marked {
  border-style: solid;
  color: var(--pm-muted, #64748b);
  border-color: var(--pm-divider, #d8dfe1);
  background: color-mix(in srgb, var(--pm-muted, #535e62) 6%, transparent);
}
.pm-ocrquote__learn.is-marked:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 55%, transparent);
  color: var(--pm-accent-strong, #00555f);
}
/* Zitate behalten unabhängig vom Lernfortschritt ihre neutrale Darstellung. */
.pm-ocrquote.pm-ocrquote.pm-learn-state {
  border-left-color: var(--pm-accent, #006b75);
  background: var(--pm-viewer-surface, #eef2f4);
}
/* Die Lernzeilen-Regeln reservieren rechts Platz für eine Status-Pille – das
   Zitat zeigt seinen Status im eigenen Fuß, braucht den Platz also nicht. */
.pm-ocrquote.pm-ocrquote.pm-learn-state { padding-right: 16px; }
.pm-ocrquote__origin { opacity: 0.8; }
</style>
