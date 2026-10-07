<!--
  DocumentLearnHighlightsSection — Gesamtübersicht der Lernmarkierungen eines
  Dokuments über alle verknüpften Notizen hinweg (Split-Ansicht-Ebene, nicht die
  Lesemodus-Markierungen). Filter nach Bedeutung; ein Klick öffnet die
  zugehörige Notiz und springt in ihrer Split-Ansicht zur Stelle.
  Erscheint nur, wenn es Lernmarkierungen gibt.
-->
<template>
  <section v-if="highlights.length" class="doc-learn" aria-label="Lernmarkierungen in diesem Dokument">
    <header class="doc-learn__header">
      <div class="doc-learn__heading">
        <span class="doc-learn__heading-icon" aria-hidden="true">
          <v-icon size="17">mdi-format-color-highlight</v-icon>
        </span>
        <span>Lernmarkierungen</span>
        <span class="doc-learn__count">{{ highlights.length }}</span>
      </div>
    </header>

    <div class="doc-learn__filters" role="group" aria-label="Nach Bedeutung filtern">
      <button
        type="button"
        class="doc-learn__filter"
        :class="{ 'is-active': !activeColor }"
        :aria-pressed="!activeColor"
        @click="activeColor = null"
      >
        Alle
      </button>
      <button
        v-for="entry in colorFilters"
        :key="entry.key"
        type="button"
        class="doc-learn__filter"
        :class="{ 'is-active': activeColor === entry.key }"
        :aria-pressed="activeColor === entry.key"
        :disabled="!entry.count"
        @click="activeColor = activeColor === entry.key ? null : entry.key"
      >
        <span class="doc-learn__dot" :style="{ background: entry.hex }" aria-hidden="true" />
        {{ entry.label }}
        <span class="doc-learn__filter-count">{{ entry.count }}</span>
      </button>
    </div>

    <ul class="doc-learn__list">
      <li v-for="highlight in visibleHighlights" :key="highlight.id">
        <button type="button" class="doc-learn__item" @click="emit('open-highlight', highlight)">
          <span
            class="doc-learn__bar"
            :style="{ background: colorFor(highlight.color).hex }"
            :title="colorFor(highlight.color).label"
            aria-hidden="true"
          />
          <span class="doc-learn__item-copy">
            <span class="doc-learn__quote" :class="{ 'is-empty': !highlight.quote }">
              {{ highlight.quote || 'Markierung ohne Text' }}
            </span>
            <span class="doc-learn__meta">
              S.&nbsp;{{ highlight.page }} · {{ colorFor(highlight.color).label }} ·
              <span class="doc-learn__note">{{ highlight.note_title?.trim() || 'Ohne Titel' }}</span>
            </span>
          </span>
          <v-icon size="16" class="doc-learn__chevron">mdi-chevron-right</v-icon>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { listDocumentLearnHighlights } from '../../api/noteLearnHighlights.js';
import { LEARN_HIGHLIGHT_COLORS, learnHighlightByKey } from './learnHighlightColors.js';

const props = defineProps({
  documentId: { type: String, default: null },
  // Erhöht sich, wenn der Aufrufer die Übersicht neu laden möchte.
  reloadKey: { type: Number, default: 0 },
});

const emit = defineEmits(['open-highlight']);

const highlights = ref([]);
const activeColor = ref(null);
let requestId = 0;

const colorFilters = computed(() => LEARN_HIGHLIGHT_COLORS.map((entry) => ({
  ...entry,
  count: highlights.value.filter((highlight) => highlight.color === entry.key).length,
})));

const visibleHighlights = computed(() => (
  activeColor.value
    ? highlights.value.filter((highlight) => highlight.color === activeColor.value)
    : highlights.value
));

function colorFor(key) {
  return learnHighlightByKey(key) || LEARN_HIGHLIGHT_COLORS[0];
}

async function load() {
  const rev = ++requestId;
  if (!props.documentId) {
    highlights.value = [];
    return;
  }
  try {
    const response = await listDocumentLearnHighlights(props.documentId);
    if (rev === requestId) highlights.value = response.items || [];
  } catch {
    // Unkritische Zusatzinfo: bei Fehlern bleibt die Übersicht einfach weg.
    if (rev === requestId) highlights.value = [];
  }
}

watch(() => props.documentId, () => {
  activeColor.value = null;
  load();
}, { immediate: true });
watch(() => props.reloadKey, load);
</script>

<style scoped>
.doc-learn {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 14px;
  background: color-mix(in srgb, var(--pm-chip-bg, #eef2f4) 62%, transparent);
}

.doc-learn__heading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--pm-text, #0e181b);
  font-size: 0.88rem;
  font-weight: 650;
}

.doc-learn__heading-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent, #006b75);
}

.doc-learn__count,
.doc-learn__filter-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 100px;
  background: color-mix(in srgb, var(--pm-muted, #535e62) 12%, transparent);
  color: var(--pm-muted, #535e62);
  font-size: 0.68rem;
  line-height: 20px;
  text-align: center;
}

.doc-learn__filter-count {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  line-height: 16px;
}

.doc-learn__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.doc-learn__filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 100px;
  background: transparent;
  color: var(--pm-text-secondary, var(--pm-muted, #535e62));
  font: inherit;
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
}

.doc-learn__filter:hover:not(:disabled) {
  background: color-mix(in srgb, var(--pm-muted, #535e62) 8%, transparent);
}

.doc-learn__filter.is-active {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 45%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent, #006b75);
}

.doc-learn__filter:disabled {
  opacity: 0.45;
  cursor: default;
}

.doc-learn__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
}

.doc-learn__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.doc-learn__item {
  display: flex;
  align-items: stretch;
  gap: 10px;
  width: 100%;
  padding: 8px 8px 8px 6px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.doc-learn__item:hover {
  background: color-mix(in srgb, var(--pm-muted, #535e62) 8%, transparent);
}

.doc-learn__bar {
  flex: 0 0 4px;
  border-radius: 4px;
}

.doc-learn__item-copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.doc-learn__quote {
  display: -webkit-box;
  overflow: hidden;
  color: var(--pm-text, #0e181b);
  font-size: 0.8rem;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.doc-learn__quote.is-empty {
  color: var(--pm-muted, #748084);
  font-style: italic;
}

.doc-learn__meta {
  overflow: hidden;
  color: var(--pm-muted, #748084);
  font-size: 0.7rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-learn__note {
  color: var(--pm-text-secondary, var(--pm-muted, #535e62));
  font-weight: 600;
}

.doc-learn__chevron {
  align-self: center;
  color: var(--pm-muted, #748084);
}
</style>
