<!--
  CorrespondentDocumentDetail — aufgeklappte Vorschau eines Dokuments im
  CorrespondentDocumentGrid: großes Vorschaubild bzw. „Seiten blättern“
  (PdfPreview) und die wichtigsten Angaben.
-->
<template>
  <div class="cdd">
    <div class="cdd__viewer" :class="{ 'is-browsing': browsing }">
      <PdfPreview
        v-if="browsing"
        :key="doc.id"
        class="cdd__pdf"
        :src="fileUrl(doc.id)"
        fit-page
      />
      <span v-else class="cdd__page" aria-hidden="true">
        <v-icon size="32">mdi-file-document-outline</v-icon>
        <img :src="thumbnail" alt="" decoding="async" @error="$event.target.hidden = true">
      </span>
    </div>
    <div class="cdd__info">
      <h4 class="cdd__heading">{{ title }}</h4>
      <dl class="cdd__facts">
        <div v-if="doc.document_type"><dt>Typ</dt><dd>{{ doc.document_type }}</dd></div>
        <div><dt>{{ doc.document_date ? 'Datum' : 'Importiert' }}</dt><dd>{{ date }}</dd></div>
        <div v-if="doc.page_count"><dt>Seiten</dt><dd>{{ doc.page_count }}</dd></div>
        <div v-if="doc.correspondent_name && doc.correspondent_name !== ownerName"><dt>Von</dt><dd>{{ doc.correspondent_name }}</dd></div>
      </dl>
      <div class="cdd__actions">
        <button type="button" class="cdd__btn" :aria-pressed="browsing" @click="emit('toggle-browsing')">
          <v-icon size="16" aria-hidden="true">{{ browsing ? 'mdi-image-outline' : 'mdi-book-open-page-variant-outline' }}</v-icon>
          {{ browsing ? 'Vorschaubild' : 'Seiten blättern' }}
        </button>
        <button type="button" class="cdd__btn" @click="emit('close')">
          <v-icon size="16" aria-hidden="true">mdi-close</v-icon>
          Schließen
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import PdfPreview from './PdfPreview.vue';
import { documentFileUrl } from '../api/documents.js';

defineProps({
  doc: { type: Object, required: true },
  title: { type: String, required: true },
  date: { type: String, required: true },
  thumbnail: { type: String, required: true },
  browsing: Boolean,
  ownerName: { type: String, default: '' },
});
const emit = defineEmits(['toggle-browsing', 'close']);

const fileUrl = (id) => documentFileUrl(id, 'searchable');
</script>

<style scoped>
.cdd {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 16px;
  padding: 12px;
  border: 1px solid var(--cdg-detail-border, var(--pm-list-divider));
  border-radius: 10px;
  background: var(--cdg-detail-bg, var(--pm-app-surface));
  box-shadow: 0 1px 3px color-mix(in srgb, #000 6%, transparent);
  animation: cdd-fade 260ms ease both;
}
@keyframes cdd-fade { from { opacity: 0; } }
.cdd__viewer { min-width: 0; }
.cdd__viewer.is-browsing { grid-column: 1 / -1; order: 2; }
.cdd__viewer.is-browsing + .cdd__info { grid-column: 1 / -1; order: 1; }
.cdd__page {
  position: relative;
  display: grid;
  place-items: center;
  height: 300px;
  color: color-mix(in srgb, var(--pm-muted) 70%, transparent);
}
.cdd__page img {
  position: absolute;
  inset: 0;
  max-width: 100%;
  max-height: 100%;
  margin: auto;
  border: 1px solid color-mix(in srgb, var(--pm-text) 10%, transparent);
  border-radius: 2px;
  background: #fff;
  box-shadow: 0 1px 3px color-mix(in srgb, #000 14%, transparent);
}
.cdd__pdf { display: block; width: 100%; height: min(70vh, 640px); border-radius: 6px; overflow: hidden; }
.cdd__info { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.cdd__heading { margin: 0; color: var(--pm-text); font-size: 0.98rem; font-weight: 650; line-height: 1.35; overflow-wrap: anywhere; }
.cdd__facts { display: grid; gap: 6px; margin: 0; font-size: 0.82rem; }
.cdd__facts div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 8px; }
.cdd__facts dt { color: var(--pm-muted); }
.cdd__facts dd { margin: 0; color: var(--pm-text); overflow-wrap: anywhere; }
.cdd__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto; }
.cdd__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--pm-list-divider);
  border-radius: 8px;
  background: transparent;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.cdd__btn:hover { background: var(--pm-list-hover); }
.cdd__btn:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }

@container (max-width: 560px) {
  .cdd { grid-template-columns: minmax(0, 1fr); }
  .cdd__page { height: 240px; }
}
@media (prefers-reduced-motion: reduce) { .cdd { animation: none; } }
:global(.pm-no-animations) .cdd { animation: none !important; }
</style>
