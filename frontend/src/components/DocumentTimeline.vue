<template>
  <div class="doc-timeline">
    <div v-if="!documents.length && !loading" class="doc-timeline__empty">
      <v-icon size="30">mdi-timeline-text-outline</v-icon>
      <p>Keine datierten Dokumente in dieser Auswahl.</p>
    </div>

    <div v-else class="doc-timeline__scroll">
      <div class="doc-timeline__body">
        <section v-for="group in groups" :key="group.year" class="doc-timeline__year">
          <header class="doc-timeline__year-head">
            <span class="doc-timeline__year-label">{{ group.yearLabel }}</span>
            <span class="doc-timeline__year-count">{{ group.count }} {{ group.count === 1 ? 'Dokument' : 'Dokumente' }}</span>
            <span class="doc-timeline__year-rule" />
          </header>

          <div class="doc-timeline__spine">
            <template v-for="mon in group.months" :key="`${group.year}-${mon.key}`">
              <div class="doc-timeline__month">{{ mon.label }}</div>
              <button
                v-for="doc in mon.items"
                :key="doc.id"
                type="button"
                class="doc-timeline__item"
                :class="{ 'doc-timeline__item--active': doc.id === selectedId }"
                @click="emit('select', doc.id)"
              >
                <span
                  class="doc-timeline__dot"
                  :class="{ 'doc-timeline__dot--unread': doc.is_unread }"
                  aria-hidden="true"
                />
                <span class="doc-timeline__thumb">
                  <img
                    v-if="!thumbError[doc.id]"
                    :src="thumbUrl(doc.id)"
                    alt=""
                    loading="lazy"
                    @error="thumbError[doc.id] = true"
                  />
                  <v-icon v-else size="18">mdi-file-outline</v-icon>
                </span>
                <span class="doc-timeline__content">
                  <span class="doc-timeline__meta">
                    <span v-if="docType(doc)" class="doc-timeline__type">{{ docType(doc) }}</span>
                    <span v-if="docCorr(doc)" class="doc-timeline__corr">· {{ docCorr(doc) }}</span>
                  </span>
                  <span class="doc-timeline__title">{{ docTitle(doc) }}</span>
                </span>
                <span class="doc-timeline__date">{{ formatDate(doc.document_date) }}</span>
                <v-icon
                  size="17"
                  class="doc-timeline__fav"
                  :class="{ 'doc-timeline__fav--on': doc.is_favorite }"
                  @click.stop="emit('toggle-favorite', doc)"
                >{{ doc.is_favorite ? 'mdi-star' : 'mdi-star-outline' }}</v-icon>
              </button>
            </template>
          </div>
        </section>

        <div v-if="hasMore" class="doc-timeline__more">
          <v-btn variant="tonal" size="small" :loading="loadingMore" @click="emit('load-more')">
            Weitere laden
          </v-btn>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue';
import { documentThumbnailUrl } from '../api/documents.js';

const props = defineProps({
  documents: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  hasMore: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  showSuffix: { type: Boolean, default: true },
});

const emit = defineEmits(['select', 'load-more', 'toggle-favorite']);

const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
const dateFormatter = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });

function parseDate(value) {
  if (!value) return null;
  const d = new Date(String(value).length <= 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDate(value) {
  const d = parseDate(value);
  return d ? dateFormatter.format(d) : '—';
}

/**
 * Gruppiert die (bereits gefilterten) Dokumente nach Jahr → Monat.
 * Ohne Dokumentdatum landen in einem eigenen Block am Ende.
 */
const groups = computed(() => {
  const byYear = new Map();
  let undated = null;

  for (const doc of props.documents) {
    const d = parseDate(doc.document_date);
    if (!d) {
      if (!undated) undated = { year: 'undated', yearLabel: 'Ohne Datum', count: 0, monthMap: new Map(), order: -Infinity };
      undated.count += 1;
      if (!undated.monthMap.has('x')) undated.monthMap.set('x', { key: 'x', label: '', order: 0, items: [] });
      undated.monthMap.get('x').items.push(doc);
      continue;
    }
    const year = d.getFullYear();
    if (!byYear.has(year)) byYear.set(year, { year, yearLabel: String(year), count: 0, monthMap: new Map(), order: year });
    const yearGroup = byYear.get(year);
    yearGroup.count += 1;
    const m = d.getMonth();
    if (!yearGroup.monthMap.has(m)) yearGroup.monthMap.set(m, { key: m, label: MONTHS[m], order: m, items: [] });
    yearGroup.monthMap.get(m).items.push(doc);
  }

  const result = [...byYear.values()];
  if (undated) result.push(undated);
  result.sort((a, b) => b.order - a.order);
  return result.map((g) => ({
    ...g,
    months: [...g.monthMap.values()].sort((a, b) => b.order - a.order),
  }));
});

const thumbError = reactive({});
const thumbUrl = (id) => documentThumbnailUrl(id);

function docTitle(doc) {
  let title = String(doc.display_name || doc.original_filename || '').trim() || 'Ohne Titel';
  if (!props.showSuffix) title = title.replace(/\.pdf$/i, '');
  return title;
}

function docType(doc) {
  return String(doc.document_type || doc.category || '').trim();
}

function docCorr(doc) {
  const c = doc.correspondent;
  return String(
    doc.correspondent_name || doc.correspondent_short_name || c?.short_name || c?.name || ''
  ).trim();
}
</script>

<style scoped>
.doc-timeline {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.doc-timeline__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.doc-timeline__body {
  padding: 8px 18px 24px;
}

.doc-timeline__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--pm-muted);
  padding: 48px 20px;
  text-align: center;
}

.doc-timeline__year {
  margin-top: 10px;
  /* Native „Virtualisierung": Offscreen-Jahre überspringen Layout/Paint.
     Granularität = ganze Jahres-Sektion, damit die überstehenden Achsen-Punkte
     (left:-25px) und die Sticky-Header nicht durch Paint-Containment leiden.
     `auto` merkt sich die zuletzt gerenderte Höhe; 480px ist nur der Startwert
     für noch nie gerenderte Jahre. */
  content-visibility: auto;
  contain-intrinsic-size: auto 480px;
}

.doc-timeline__year-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 8px 0 6px;
  background: var(--pm-content-surface);
}

.doc-timeline__year-label {
  font-size: 19px;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--pm-text);
}

.doc-timeline__year-count {
  font-size: 12.5px;
  color: var(--pm-muted);
}

.doc-timeline__year-rule {
  flex: 1;
  height: 1px;
  background: var(--pm-divider);
}

.doc-timeline__spine {
  border-left: 2px solid var(--pm-divider);
  margin-left: 7px;
  padding-left: 18px;
}

.doc-timeline__month {
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--pm-muted);
  margin: 12px 0 4px;
}

.doc-timeline__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.14s ease, border-color 0.14s ease;
}

.doc-timeline__item:hover {
  background: var(--pm-row-hover, rgba(var(--v-theme-on-surface), 0.04));
}

.doc-timeline__item--active {
  background: var(--pm-row-active, color-mix(in srgb, var(--pm-accent) 12%, transparent));
  border-color: color-mix(in srgb, var(--pm-accent) 34%, transparent);
}

.doc-timeline__dot {
  position: absolute;
  left: -25px;
  top: 50%;
  transform: translateY(-50%);
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--pm-muted);
  border: 2px solid var(--pm-content-surface);
}

.doc-timeline__dot--unread { background: var(--pm-accent); }

.doc-timeline__thumb {
  width: 34px;
  height: 44px;
  border-radius: 5px;
  flex: none;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid var(--pm-divider);
  color: var(--pm-muted);
}

.doc-timeline__thumb img { width: 100%; height: 100%; object-fit: cover; }

.doc-timeline__content { flex: 1; min-width: 0; display: flex; flex-direction: column; }

.doc-timeline__meta {
  font-size: 11.5px;
  color: var(--pm-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-timeline__type { font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; }

.doc-timeline__title {
  font-size: 14px;
  font-weight: 500;
  color: var(--pm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.doc-timeline__date {
  flex: none;
  font-size: 12px;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
}

.doc-timeline__fav {
  flex: none;
  color: var(--pm-muted) !important;
  opacity: 0;
  transition: opacity 0.14s ease, color 0.14s ease;
}

.doc-timeline__item:hover .doc-timeline__fav { opacity: 1; }
.doc-timeline__fav--on { color: var(--pm-warning) !important; opacity: 1; }

.doc-timeline__more {
  display: flex;
  justify-content: center;
  padding: 18px 0 6px;
}
</style>
