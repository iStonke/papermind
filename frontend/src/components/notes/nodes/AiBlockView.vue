<template>
  <node-view-wrapper
    class="pm-aiblock"
    :class="{ 'is-selected': selected, 'is-arriving': isArriving }"
    contenteditable="false"
  >
    <div class="pm-aiblock__head">
      <span class="pm-aiblock__label">
        <span aria-hidden="true">✦</span>
        KI-generiert<template v-if="providerDetails"> · {{ providerDetails }}</template><template v-if="sources.length"> · {{ sources.length }} {{ sources.length === 1 ? 'Quelle' : 'Quellen' }}</template>
      </span>
      <span class="pm-aiblock__actions">
        <button
          v-if="node.attrs.prompt"
          class="pm-aiblock__action"
          type="button"
          :aria-expanded="showPrompt"
          @click="showPrompt = !showPrompt"
        >Prompt</button>
        <button
          v-if="editor.isEditable"
          class="pm-aiblock__action"
          type="button"
          title="Kennzeichnung entfernen und als normalen Text übernehmen"
          @click="convertToText"
        >Übernehmen</button>
        <button
          v-if="node.attrs.stale"
          class="pm-aiblock__stale"
          type="button"
          title="Eine Quelle hat sich seit der Antwort geändert"
        >veraltet?</button>
      </span>
    </div>

    <div v-if="showPrompt" class="pm-aiblock__prompt">{{ node.attrs.prompt }}</div>

    <div class="pm-aiblock__body">
      <template v-for="(block, blockIndex) in markdownBlocks" :key="blockIndex">
        <p v-if="block.type === 'paragraph'" :style="arrivalDelay(blockIndex)">
          <AiMarkdownInline :segments="block.segments" />
        </p>
        <ul v-else-if="block.type === 'bulletList'" :style="arrivalDelay(blockIndex)">
          <li v-for="(segments, itemIndex) in block.items" :key="itemIndex">
            <AiMarkdownInline :segments="segments" />
          </li>
        </ul>
        <ol v-else-if="block.type === 'orderedList'" :start="block.start" :style="arrivalDelay(blockIndex)">
          <li v-for="(segments, itemIndex) in block.items" :key="itemIndex">
            <AiMarkdownInline :segments="segments" />
          </li>
        </ol>
        <div v-else-if="block.type === 'table'" class="pm-aiblock__table-wrap" :style="arrivalDelay(blockIndex)">
          <table>
            <thead>
              <tr>
                <th v-for="(segments, cellIndex) in block.header" :key="cellIndex">
                  <AiMarkdownInline :segments="segments" />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in block.rows" :key="rowIndex">
                <td v-for="(segments, cellIndex) in row" :key="cellIndex">
                  <AiMarkdownInline :segments="segments" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <div v-if="sources.length" class="pm-aiblock__sources">
      <button
        v-for="(s, i) in sources"
        :key="i"
        class="pm-aiblock__src"
        type="button"
        @click="openSource(s)"
      >
        <span aria-hidden="true">▢</span>
        {{ s.title }}<template v-if="s.page"> · S.&nbsp;{{ s.page }}</template>
      </button>
    </div>
  </node-view-wrapper>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';
import { noteMarkdownToTipTap, parseNoteMarkdown } from '../../../utils/noteMarkdown.js';
import AiMarkdownInline from './AiMarkdownInline.vue';

const props = defineProps(nodeViewProps);
const sources = computed(() => props.node.attrs.sources || []);
const showPrompt = ref(false);
const isArriving = ref(false);
const markdownBlocks = computed(() => parseNoteMarkdown(props.node.attrs.text));
const providerDetails = computed(() => {
  const provider = { ollama: 'Lokal', openai: 'OpenAI', anthropic: 'Claude' }[props.node.attrs.provider] || '';
  const model = String(props.node.attrs.model || '').trim();
  return [provider, model].filter(Boolean).join(' · ');
});
let arrivalTimer = null;

onMounted(() => {
  const generatedAt = Date.parse(props.node.attrs.generatedAt || '');
  if (!Number.isFinite(generatedAt) || Math.abs(Date.now() - generatedAt) > 4000) return;
  isArriving.value = true;
  arrivalTimer = window.setTimeout(() => {
    isArriving.value = false;
    arrivalTimer = null;
  }, 1100);
});

onBeforeUnmount(() => {
  if (arrivalTimer) window.clearTimeout(arrivalTimer);
});

function arrivalDelay(index) {
  return { '--pm-ai-arrival-delay': `${Math.min(index, 6) * 55}ms` };
}

function openSource(s) {
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: { type: 'document', id: s.docId, label: s.title, page: s.page },
  }));
}

function convertToText() {
  if (!props.editor.isEditable) return;
  const from = props.getPos();
  if (!Number.isInteger(from)) return;
  const content = noteMarkdownToTipTap(props.node.attrs.text);
  props.editor.chain().focus().insertContentAt(
    { from, to: from + props.node.nodeSize },
    content.length ? content : [{ type: 'paragraph' }],
  ).run();
}
</script>

<style scoped>
.pm-aiblock {
  --pm-ai: var(--pm-warning, #b45309);
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border: 1px dashed color-mix(in srgb, var(--pm-ai) 55%, transparent);
  background: color-mix(in srgb, var(--pm-ai) 9%, transparent);
  border-radius: 10px;
  padding: 12px 15px;
  margin: 0.7em 0;
}
.pm-aiblock > * { position: relative; z-index: 1; }
.pm-aiblock.is-arriving {
  animation: pm-aiblock-arrive 520ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.pm-aiblock.is-arriving::after {
  content: '';
  position: absolute;
  z-index: 0;
  top: -45%;
  bottom: -45%;
  left: 0;
  width: 38%;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--pm-ai) 22%, transparent), transparent);
  transform: translateX(-150%) skewX(-16deg);
  animation: pm-aiblock-sweep 760ms ease-out both;
}
.pm-aiblock.is-arriving .pm-aiblock__label {
  animation: pm-aiblock-label 900ms ease-out both;
}
.pm-aiblock.is-arriving .pm-aiblock__body > * {
  animation: pm-aiblock-content 360ms cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--pm-ai-arrival-delay, 0ms);
}
.pm-aiblock.is-selected {
  outline: 2px solid color-mix(in srgb, var(--pm-ai) 50%, transparent);
  outline-offset: 2px;
}
.pm-aiblock__head {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-bottom: 7px;
}
.pm-aiblock__actions { display: inline-flex; align-items: center; gap: 5px; }
.pm-aiblock__label {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.66rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--pm-ai);
  display: inline-flex; align-items: center; gap: 6px;
}
.pm-aiblock__action {
  border: 0; background: transparent; color: var(--pm-muted, #535e62);
  font-size: 0.68rem; padding: 2px 5px; border-radius: 5px; cursor: pointer;
}
.pm-aiblock__action:hover { background: color-mix(in srgb, var(--pm-ai) 10%, transparent); color: var(--pm-ai); }
.pm-aiblock__stale {
  border: 1px solid color-mix(in srgb, var(--pm-ai) 50%, transparent); background: transparent;
  color: var(--pm-ai);
  font-size: 0.66rem; padding: 1px 7px; border-radius: 100px; cursor: pointer;
}
.pm-aiblock__prompt {
  margin: 0 0 8px; padding: 7px 9px; border-radius: 6px;
  background: color-mix(in srgb, var(--pm-ai) 7%, transparent);
  color: var(--pm-muted, #535e62); font-size: 0.75rem; line-height: 1.4;
}
.pm-aiblock__body { color: var(--pm-text, #0e181b); line-height: 1.6; }
.pm-aiblock__body p { margin: 0; }
.pm-aiblock__body p + p { margin-top: 0.65em; }
.pm-aiblock__body ul,
.pm-aiblock__body ol { margin: 0.2em 0 0.15em; padding-left: 1.35em; }
.pm-aiblock__body li { padding-left: 0.12em; }
.pm-aiblock__body li + li { margin-top: 0.2em; }
.pm-aiblock__table-wrap {
  max-width: 100%;
  margin-top: 0.35em;
  overflow-x: auto;
  border-radius: 7px;
}
.pm-aiblock__table-wrap table {
  width: 100%;
  min-width: 320px;
  border: 1px solid color-mix(in srgb, var(--pm-ai) 28%, var(--pm-divider, #d8dfe1));
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 7px;
  font-size: 0.82rem;
}
.pm-aiblock__table-wrap th,
.pm-aiblock__table-wrap td {
  padding: 6px 8px;
  border-right: 1px solid var(--pm-divider, #d8dfe1);
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  text-align: left;
  vertical-align: top;
}
.pm-aiblock__table-wrap th:last-child,
.pm-aiblock__table-wrap td:last-child { border-right: 0; }
.pm-aiblock__table-wrap tbody tr:last-child td { border-bottom: 0; }
.pm-aiblock__table-wrap th {
  background: color-mix(in srgb, var(--pm-ai) 10%, transparent);
  color: var(--pm-text, #0e181b);
  font-weight: 650;
}
.pm-aiblock__sources { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.pm-aiblock__src {
  border: 1px solid var(--pm-divider, #d8dfe1);
  background: var(--pm-app-surface, #fff);
  color: var(--pm-muted, #535e62);
  font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 0.7rem;
  padding: 3px 8px; border-radius: 6px; cursor: pointer;
  display: inline-flex; align-items: baseline; gap: 5px;
}
.pm-aiblock__src:hover { color: var(--pm-accent-strong, #00555f); border-color: var(--pm-accent, #006b75); }

@keyframes pm-aiblock-arrive {
  from { opacity: 0; transform: translateY(7px) scale(0.992); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes pm-aiblock-sweep {
  from { transform: translateX(-150%) skewX(-16deg); }
  to { transform: translateX(390%) skewX(-16deg); }
}
@keyframes pm-aiblock-label {
  0% { filter: drop-shadow(0 0 0 transparent); }
  42% { filter: drop-shadow(0 0 6px color-mix(in srgb, var(--pm-ai) 58%, transparent)); }
  100% { filter: drop-shadow(0 0 0 transparent); }
}
@keyframes pm-aiblock-content {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .pm-aiblock.is-arriving,
  .pm-aiblock.is-arriving::after,
  .pm-aiblock.is-arriving .pm-aiblock__label,
  .pm-aiblock.is-arriving .pm-aiblock__body > * { animation: none; }
}

:global(.pm-no-animations) .pm-aiblock.is-arriving,
:global(.pm-no-animations) .pm-aiblock.is-arriving::after,
:global(.pm-no-animations) .pm-aiblock.is-arriving .pm-aiblock__label,
:global(.pm-no-animations) .pm-aiblock.is-arriving .pm-aiblock__body > * {
  animation: none;
}
</style>
