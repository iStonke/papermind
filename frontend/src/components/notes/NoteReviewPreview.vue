<template>
  <div class="pm-review-preview" @click.capture="preventNavigation">
    <div v-if="structured" class="pm-review-preview__label">Vorschau</div>
    <div class="pm-review-preview__content" v-html="html" />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { noteMarkdownToSafeHtml } from '../../utils/noteMarkdown.js';
const props = defineProps({ text: { type: String, default: '' }, structured: Boolean });
// Same Markdown grammar as acceptance; all text and links are escaped/validated.
const html = computed(() => noteMarkdownToSafeHtml(props.text));
function preventNavigation(event) {
  if (event.target.closest('a')) event.preventDefault();
}
</script>

<style scoped>
.pm-review-preview { min-width: 0; }
.pm-review-preview__label { margin-bottom: 6px; color: var(--pm-muted); font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.pm-review-preview__content { max-height: 280px; overflow: auto; overflow-wrap: anywhere; color: var(--pm-text); line-height: 1.5; }
.pm-review-preview__content :deep(p) { margin: 0; }
.pm-review-preview__content :deep(p + p) { margin-top: 0.65em; }
.pm-review-preview__content :deep(h1), .pm-review-preview__content :deep(h2), .pm-review-preview__content :deep(h3) { margin: 0.3em 0; font-size: 1.1em; line-height: 1.35; }
.pm-review-preview__content :deep(ul), .pm-review-preview__content :deep(ol) { padding-left: 1.4em; }
.pm-review-preview__content :deep([data-type="taskList"]) { padding-left: 0; list-style: none; }
.pm-review-preview__content :deep([data-type="taskList"] li) { display: flex; gap: 6px; align-items: baseline; }
.pm-review-preview__content :deep(aside), .pm-review-preview__content :deep(blockquote) { margin: 0; padding: 9px 11px; border: 1px solid color-mix(in srgb, var(--preview-callout-color, var(--pm-accent)) 28%, transparent); border-left: 3px solid var(--preview-callout-color, var(--pm-accent)); border-radius: 7px; background: color-mix(in srgb, var(--preview-callout-color, var(--pm-accent)) 7%, var(--pm-content-surface)); }
.pm-review-preview__content :deep(aside[data-callout="info"]) { --preview-callout-color: #2878b5; }
.pm-review-preview__content :deep(aside[data-callout="important"]) { --preview-callout-color: var(--pm-warning, #b7791f); }
.pm-review-preview__content :deep(aside[data-callout="decision"]) { --preview-callout-color: #2f855a; }
.pm-review-preview__content :deep(aside[data-callout="prompt"]) { --preview-callout-color: #7c5aa6; }
.pm-review-preview__content :deep(aside::before) { content: 'Information'; display: block; margin-bottom: 4px; font-size: 10px; font-weight: 650; color: var(--preview-callout-color, var(--pm-accent)); }
.pm-review-preview__content :deep(aside[data-callout="important"]::before) { content: 'Wichtig'; }
.pm-review-preview__content :deep(aside[data-callout="question"]::before) { content: 'Frage'; }
.pm-review-preview__content :deep(aside[data-callout="decision"]::before) { content: 'Entscheidung'; }
.pm-review-preview__content :deep(aside[data-callout="prompt"]::before) { content: 'Prompt'; }
.pm-review-preview__content :deep(.table-wrap) { overflow-x: auto; }
.pm-review-preview__content :deep(table) { width: 100%; border-collapse: collapse; font-size: 0.95em; }
.pm-review-preview__content :deep(th), .pm-review-preview__content :deep(td) { min-width: 70px; padding: 5px 7px; border: 1px solid var(--pm-divider); text-align: left; vertical-align: top; }
.pm-review-preview__content :deep(th) { background: color-mix(in srgb, var(--pm-accent) 7%, var(--pm-content-surface)); }
.pm-review-preview__content :deep(pre) { overflow-x: auto; }
.pm-review-preview__content :deep(a) { color: var(--pm-accent-text); }
</style>
