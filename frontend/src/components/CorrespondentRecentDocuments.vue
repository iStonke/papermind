<template>
  <ul
    v-if="documents.length"
    class="pm-recent-docs"
    :class="{ 'pm-recent-docs--peek': documents.length > 3 }"
    :tabindex="documents.length > 1 ? 0 : undefined"
    :aria-busy="loadingMore || undefined"
    aria-label="Neuste Dokumente"
    @scroll.passive="loadMoreNearEnd"
  >
    <li v-for="doc in documents" :key="doc.id">
      <button
        type="button"
        class="pm-recent-docs__card"
        @click="emit('open', doc.id)"
      >
        <span class="pm-recent-docs__page" aria-hidden="true">
          <v-icon size="28">mdi-file-document-outline</v-icon>
          <img
            :key="doc.updated_at"
            :src="thumbnailSrc(doc)"
            alt=""
            loading="lazy"
            decoding="async"
            @error="$event.target.hidden = true"
          >
        </span>
        <span class="pm-recent-docs__copy">
          <strong :title="titleOf(doc)">{{ titleOf(doc) }}</strong>
          <span v-if="doc.document_type" class="pm-recent-docs__type">{{ doc.document_type }}</span>
          <span class="pm-recent-docs__date">
            {{ formatDate(doc.document_date || doc.created_at) }}
            <small v-if="!doc.document_date && doc.created_at">Importiert</small>
          </span>
        </span>
      </button>
    </li>
  </ul>
  <div v-else class="pm-recent-docs__card pm-recent-docs__card--compact pm-recent-docs__empty">
    <span class="pm-recent-docs__page" aria-hidden="true">
      <v-icon size="28">mdi-file-document-outline</v-icon>
    </span>
    <div class="pm-recent-docs__copy">
      <strong>Noch keine Dokumente</strong>
      <span class="pm-recent-docs__hint">{{ emptyDescription }}</span>
    </div>
  </div>
</template>

<script setup>
import { documentThumbnailUrl } from '../api/documents.js';

const props = defineProps({
  documents: { type: Array, required: true },
  emptyDescription: { type: String, required: true },
  hasMore: Boolean,
  loadingMore: Boolean,
  loadMoreFailed: Boolean,
});
const emit = defineEmits(['open', 'load-more']);

function loadMoreNearEnd({ currentTarget: list }) {
  if (!props.hasMore || props.loadingMore || props.loadMoreFailed) return;
  if (list.scrollWidth - list.clientWidth - list.scrollLeft <= list.clientWidth / 2) {
    emit('load-more');
  }
}

function thumbnailSrc(doc) {
  const base = documentThumbnailUrl(doc.id);
  const version = encodeURIComponent(doc.updated_at || '');
  return `${base}${base.includes('?') ? '&' : '?'}thumb_v=${version}`;
}

function titleOf(doc) {
  return String(doc.display_name || doc.original_filename || '').trim() || 'Ohne Titel';
}

function formatDate(iso) {
  if (!iso) return '–';
  const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
</script>

<style scoped>
.pm-recent-docs {
  --recent-doc-gap: 12px;
  --recent-doc-peek: 0px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: min(100%, max(166px, calc((100% - 2 * var(--recent-doc-gap) - var(--recent-doc-peek)) / 3)));
  gap: var(--recent-doc-gap);
  margin: 0;
  padding: 0;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--pm-outline) transparent;
  list-style: none;
}
.pm-recent-docs--peek { --recent-doc-peek: 30px; }
.pm-recent-docs:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.pm-recent-docs__card {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--pm-list-divider);
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  text-align: start;
}
button.pm-recent-docs__card { height: 100%; cursor: pointer; }
button.pm-recent-docs__card:hover { background: var(--pm-list-hover); }
button.pm-recent-docs__card:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -2px; }
.pm-recent-docs__page {
  position: relative;
  display: grid;
  place-items: center;
  flex: none;
  width: 100%;
  height: 148px;
  background: var(--pm-list-hover);
}
.pm-recent-docs__page img {
  position: absolute;
  inset: 8px;
  width: calc(100% - 16px);
  height: calc(100% - 16px);
  object-fit: contain;
}
.pm-recent-docs__copy {
  box-sizing: border-box;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 12px 11px;
  overflow-wrap: anywhere;
}
.pm-recent-docs__copy strong {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  min-block-size: 2lh;
  overflow: hidden;
  color: var(--pm-list-title);
  font-size: 0.89rem;
  font-weight: 500;
  line-height: 1.35;
}
.pm-recent-docs__type, .pm-recent-docs__date, .pm-recent-docs__hint { font-size: 0.76rem; }
.pm-recent-docs__type {
  align-self: flex-start;
  max-width: 100%;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  color: var(--pm-accent-text);
  font-weight: 600;
}
.pm-recent-docs__date {
  margin-top: auto;
  padding-top: 2px;
  font-variant-numeric: tabular-nums;
}
.pm-recent-docs__date small { margin-inline-start: 4px; font-size: inherit; }

.pm-recent-docs__card--compact { flex-direction: row; }
.pm-recent-docs__card--compact .pm-recent-docs__page { width: 76px; height: auto; min-height: 88px; }
.pm-recent-docs__card--compact .pm-recent-docs__copy { min-width: 0; width: auto; justify-content: center; padding: 10px 14px; }
.pm-recent-docs__card--compact .pm-recent-docs__copy strong { min-block-size: 0; }
.pm-recent-docs__card--compact .pm-recent-docs__date { margin-top: 0; padding-top: 0; }
.pm-recent-docs__empty { width: 50%; }
.pm-recent-docs__empty strong { -webkit-line-clamp: unset; }
.pm-recent-docs__empty .pm-recent-docs__page {
  background: color-mix(in srgb, var(--pm-accent) 9%, var(--pm-app-surface));
  color: var(--pm-accent-text);
}
@container (max-width: 440px) {
  .pm-recent-docs__card--compact { flex-direction: column; }
  .pm-recent-docs__card--compact .pm-recent-docs__page { width: 100%; height: 88px; }
  .pm-recent-docs__card--compact .pm-recent-docs__copy { width: 100%; padding: 10px; }
}
</style>
