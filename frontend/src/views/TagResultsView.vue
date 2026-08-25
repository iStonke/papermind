<!--
  TagResultsView — kombinierte Trefferseite für ein Tag (T3). Zeigt Dokumente
  UND Notizen mit demselben Tag, in getrennten Blöcken. Nutzt das gemeinsame
  Tag-Vokabular (note_tags reuse tags-Tabelle). Klicks öffnen das jeweilige
  Objekt über Events des DocumentsWorkspace.
-->
<template>
  <section class="tag-results panel" aria-label="Tag-Treffer">
    <div class="tag-results__scroll">
      <header class="tag-results__head">
        <span class="tag-results__eyebrow"><v-icon size="14">mdi-tag</v-icon> Tag</span>
        <h1 class="tag-results__title">{{ tagName || 'Tag' }}</h1>
        <p class="tag-results__summary">
          {{ documents.length }} {{ documents.length === 1 ? 'Dokument' : 'Dokumente' }}
          · {{ notes.length }} {{ notes.length === 1 ? 'Notiz' : 'Notizen' }}
        </p>
      </header>

      <div v-if="isLoading" class="tag-results__state" aria-live="polite">
        <v-progress-circular indeterminate color="primary" size="26" width="2" />
        <span>Treffer werden geladen …</span>
      </div>

      <div v-else-if="!documents.length && !notes.length" class="tag-results__state">
        <v-icon size="30">mdi-tag-off-outline</v-icon>
        <span>Nichts mit diesem Tag verknüpft.</span>
      </div>

      <template v-else>
        <!-- Dokumente -->
        <section v-if="documents.length" class="tag-results__block">
          <h2 class="tag-results__block-title">
            <v-icon size="16">mdi-file-document-outline</v-icon>
            Dokumente <span class="tag-results__block-count">{{ documents.length }}</span>
          </h2>
          <ul class="tag-results__grid">
            <li v-for="doc in documents" :key="doc.id">
              <button type="button" class="tag-card tag-card--doc" @click="$emit('open-document', doc.id)">
                <span class="tag-card__thumb">
                  <img
                    v-if="!thumbError[doc.id]"
                    :src="documentThumbnailUrl(doc.id)"
                    alt=""
                    loading="lazy"
                    @error="thumbError[doc.id] = true"
                  />
                  <v-icon v-else size="20">mdi-file-outline</v-icon>
                </span>
                <span class="tag-card__text">
                  <span class="tag-card__title">{{ docTitle(doc) }}</span>
                  <span class="tag-card__meta">{{ doc.correspondent_name || 'Ohne Korrespondent' }}</span>
                  <span class="tag-card__meta tag-card__meta--muted">{{ formatDate(doc.document_date) }}</span>
                </span>
              </button>
            </li>
          </ul>
        </section>

        <!-- Notizen -->
        <section v-if="notes.length" class="tag-results__block">
          <h2 class="tag-results__block-title">
            <v-icon size="16">mdi-note-outline</v-icon>
            Notizen <span class="tag-results__block-count">{{ notes.length }}</span>
          </h2>
          <ul class="tag-results__grid">
            <li v-for="note in notes" :key="note.id">
              <button type="button" class="tag-card tag-card--note" @click="$emit('open-note', note.id)">
                <span class="tag-card__title" :class="{ 'is-untitled': !note.title?.trim() }">
                  {{ note.title?.trim() || 'Ohne Titel' }}
                </span>
                <span class="tag-card__snippet">{{ note.preview || 'Leere Notiz' }}</span>
                <span v-if="(note.tags || []).length" class="tag-card__chips">
                  <span v-for="t in note.tags" :key="t.id" class="tag-card__chip">{{ t.name }}</span>
                </span>
              </button>
            </li>
          </ul>
        </section>
      </template>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, watch } from 'vue';
import { listDocuments, documentThumbnailUrl } from '../api/documents.js';
import { listNotes } from '../api/notes.js';

const props = defineProps({
  tagId: { type: String, default: null },
  tagName: { type: String, default: '' },
});

defineEmits(['open-document', 'open-note']);

const documents = ref([]);
const notes = ref([]);
const isLoading = ref(false);
const thumbError = reactive({});
let requestSeq = 0;

async function load(tagId) {
  if (!tagId) { documents.value = []; notes.value = []; return; }
  const seq = ++requestSeq;
  isLoading.value = true;
  try {
    const [docRes, noteRes] = await Promise.all([
      listDocuments(`tag_id=${encodeURIComponent(tagId)}`).catch(() => ({ items: [] })),
      listNotes({ tagId }).catch(() => ({ items: [] })),
    ]);
    if (seq !== requestSeq) return; // veraltete Antwort verwerfen
    documents.value = docRes?.items || [];
    notes.value = noteRes?.items || [];
  } finally {
    if (seq === requestSeq) isLoading.value = false;
  }
}

function docTitle(doc) {
  return String(doc.display_name || doc.original_filename || '').trim() || 'Ohne Titel';
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

watch(() => props.tagId, (id) => load(id), { immediate: true });
</script>

<style scoped>
.tag-results {
  display: flex;
  min-height: 0;
  flex-direction: column;
  background: var(--pm-app-surface, #fff);
}
.tag-results__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 28px clamp(20px, 4vw, 56px) 48px;
}

.tag-results__head { margin-bottom: 28px; }
.tag-results__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--pm-accent-strong, #00666f);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.tag-results__title {
  margin: 6px 0 4px;
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 650;
  color: var(--pm-text, #0f172a);
  line-height: 1.15;
}
.tag-results__summary { margin: 0; color: var(--pm-muted, #64748b); font-size: 0.9rem; }

.tag-results__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 64px 0;
  color: var(--pm-muted, #64748b);
}

.tag-results__block { margin-top: 30px; }
.tag-results__block-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 14px;
  font-size: 0.95rem;
  font-weight: 650;
  color: var(--pm-text, #0f172a);
}
.tag-results__block-count {
  color: var(--pm-muted, #64748b);
  font-weight: 500;
}
.tag-results__grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.tag-card {
  width: 100%;
  height: 100%;
  text-align: left;
  cursor: pointer;
  border: 1px solid var(--pm-divider, #e2e8f0);
  border-radius: 14px;
  background: var(--pm-content-surface, #fff);
  padding: 14px;
  transition: border-color 130ms ease, box-shadow 130ms ease, transform 130ms ease;
}
.tag-card:hover {
  border-color: rgba(var(--v-theme-primary, 0 107 117), 0.5);
  box-shadow: 0 6px 18px -10px rgba(0, 0, 0, 0.35);
  transform: translateY(-1px);
}

.tag-card--doc { display: flex; align-items: center; gap: 12px; }
.tag-card__thumb {
  flex: none;
  width: 44px;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--pm-viewer-surface, #f1f5f9);
  color: var(--pm-muted, #94a3b8);
}
.tag-card__thumb img { width: 100%; height: 100%; object-fit: cover; }
.tag-card__text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }

.tag-card--note { display: flex; flex-direction: column; gap: 6px; }
.tag-card__title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--pm-text, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag-card__title.is-untitled { color: var(--pm-muted, #94a3b8); font-style: italic; font-weight: 500; }
.tag-card__meta {
  font-size: 0.78rem;
  color: var(--pm-muted, #64748b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag-card__meta--muted { font-size: 0.72rem; opacity: 0.8; }
.tag-card__snippet {
  font-size: 0.8rem;
  color: var(--pm-muted, #64748b);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.tag-card__chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.tag-card__chip {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.1));
  color: var(--pm-accent-strong, #00555f);
  font-size: 0.68rem;
  font-weight: 500;
}

@media (prefers-reduced-motion: reduce) {
  .tag-card { transition: none; }
  .tag-card:hover { transform: none; }
}
</style>
