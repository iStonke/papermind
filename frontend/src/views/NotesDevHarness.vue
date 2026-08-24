<!--
  NotesDevHarness — M0-Prüfstand für den Notizen-Editor, ausgebaut zu MEHR
  Notizen (Vorgriff auf M3: Liste ↔ Editor, „Neue Notiz", Umschalten, Löschen).
  NUR im Dev-Build (Route in router/index.js hinter import.meta.env.DEV). Kein
  Backend: die Sammlung liegt im localStorage. Ab M2/M3 ersetzt ein Pinia-Store
  + Backend diese localStorage-Schicht; der NoteEditor bleibt unverändert, weil
  er persistenz-agnostisch ist.
-->
<template>
  <v-app class="papermind-app" :theme="themeName">
    <div class="dev-harness">
      <header class="dev-harness__bar">
        <div class="dev-harness__brand">
          <span class="dev-harness__mark">M0</span>
          <div>
            <div class="dev-harness__title">Notizen-Editor · Prüfstand</div>
            <div class="dev-harness__sub">{{ notes.length }} {{ notes.length === 1 ? 'Notiz' : 'Notizen' }} · localStorage · kein Backend</div>
          </div>
        </div>
        <div class="dev-harness__actions">
          <button type="button" class="dev-btn" @click="toggleTheme">
            {{ themeName === 'dark' ? '☀︎ Hell' : '☾ Dunkel' }}
          </button>
        </div>
      </header>

      <div class="dev-harness__body">
        <!-- Notizenliste -->
        <aside class="dev-list">
          <button type="button" class="dev-list__new" @click="createNote">
            <span class="dev-list__plus">＋</span> Neue Notiz
          </button>

          <div v-if="!notes.length" class="dev-list__empty">
            Noch keine Notizen.<br />Mit „Neue Notiz" beginnen.
          </div>

          <ul v-else class="dev-list__items">
            <li
              v-for="note in sortedNotes"
              :key="note.id"
              class="dev-list__item"
              :class="{ 'is-active': note.id === activeId }"
              @click="selectNote(note.id)"
            >
              <div class="dev-list__row">
                <span class="dev-list__name">{{ note.title || 'Ohne Titel' }}</span>
                <button
                  type="button"
                  class="dev-list__del"
                  title="Notiz löschen"
                  aria-label="Notiz löschen"
                  @click.stop="deleteNote(note.id)"
                >✕</button>
              </div>
              <div class="dev-list__meta">
                <span class="dev-list__snippet">{{ snippet(note) }}</span>
              </div>
              <div class="dev-list__date">{{ formatDate(note.updatedAt) }}</div>
            </li>
          </ul>
        </aside>

        <!-- Editor -->
        <main class="dev-harness__stage">
          <div v-if="activeNote" class="dev-harness__sheet">
            <NoteEditor
              ref="editorRef"
              :key="activeId"
              v-model="body"
              v-model:title="title"
              :status="status"
              @change="onBodyChange"
            />
          </div>
          <div v-else class="dev-harness__blank">
            <div class="dev-harness__blank-inner">
              <div class="dev-harness__blank-mark">✎</div>
              <p>Keine Notiz geöffnet.</p>
              <button type="button" class="dev-btn dev-btn--accent" @click="createNote">Neue Notiz anlegen</button>
            </div>
          </div>
        </main>
      </div>
    </div>
  </v-app>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import NoteEditor from '../components/notes/NoteEditor.vue';

const STORAGE_KEY = 'pm.dev.notes.v2';

const notes = ref([]);
const activeId = ref(null);
const title = ref('');
const body = ref(null);
const lastText = ref('');
const status = ref('idle'); // 'idle' | 'saving' | 'saved'
const themeName = ref('light');
const editorRef = ref(null);

// Beim Umschalten wird der Editor mit fremdem Inhalt befüllt – in dieser Phase
// KEIN Autosave, sonst überschreibt der Ladevorgang die frisch geladene Notiz.
let loading = false;
let saveTimer = null;

/* ── Laden ───────────────────────────────────────────────────────────────── */
try {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw) notes.value = JSON.parse(raw) || [];
} catch { notes.value = []; }

if (notes.value.length) {
  openNote(notes.value.slice().sort(byUpdated)[0].id);
}

const activeNote = computed(() => notes.value.find(n => n.id === activeId.value) || null);
const sortedNotes = computed(() => notes.value.slice().sort(byUpdated));

function byUpdated(a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); }

/* ── Persistenz ──────────────────────────────────────────────────────────── */
function persist() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(notes.value));
  } catch { /* Quota o. ä. – im Prüfstand unkritisch */ }
}

function scheduleSave() {
  if (loading) return;
  status.value = 'saving';
  if (saveTimer) window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    const note = activeNote.value;
    if (note) {
      note.title = title.value;
      note.body = body.value;
      note.text = lastText.value;
      note.updatedAt = Date.now();
    }
    persist();
    status.value = 'saved';
  }, 600);
}

function onBodyChange({ text }) {
  lastText.value = text;
  scheduleSave();
}
watch(title, () => scheduleSave());

/* ── Notiz-Aktionen ──────────────────────────────────────────────────────── */
function openNote(id) {
  loading = true;
  const note = notes.value.find(n => n.id === id);
  activeId.value = id;
  title.value = note?.title || '';
  body.value = note?.body || { type: 'doc', content: [{ type: 'paragraph' }] };
  lastText.value = note?.text || '';
  status.value = note ? 'saved' : 'idle';
  // Erst nach dem DOM-Update (Editor hat neuen Inhalt übernommen) Autosave wieder scharf.
  nextTick(() => { loading = false; });
}

function selectNote(id) {
  if (id === activeId.value) return;
  if (saveTimer) { window.clearTimeout(saveTimer); flushSave(); }
  openNote(id);
}

function flushSave() {
  const note = activeNote.value;
  if (note && !loading) {
    note.title = title.value;
    note.body = body.value;
    note.text = lastText.value;
    note.updatedAt = Date.now();
    persist();
  }
}

function createNote() {
  if (saveTimer) { window.clearTimeout(saveTimer); flushSave(); }
  const now = Date.now();
  const note = {
    id: (crypto?.randomUUID?.() || `n_${now}_${Math.random().toString(36).slice(2)}`),
    title: '',
    body: { type: 'doc', content: [{ type: 'paragraph' }] },
    text: '',
    createdAt: now,
    updatedAt: now,
  };
  notes.value.unshift(note);
  persist();
  openNote(note.id);
  // Sofort in den Titel springen (Sofort-Anlegen ohne Formular).
  nextTick(() => editorRef.value?.focusTitle?.());
}

function deleteNote(id) {
  const note = notes.value.find(n => n.id === id);
  const label = note?.title?.trim() || 'diese Notiz';
  if (!window.confirm(`„${label}" löschen?`)) return;
  const wasActive = id === activeId.value;
  notes.value = notes.value.filter(n => n.id !== id);
  persist();
  if (wasActive) {
    const next = sortedNotes.value[0];
    if (next) openNote(next.id);
    else { activeId.value = null; title.value = ''; body.value = null; }
  }
}

/* ── Liste: Darstellung ──────────────────────────────────────────────────── */
function snippet(note) {
  const t = (note.text || '').trim().replace(/\s+/g, ' ');
  return t ? t.slice(0, 64) : 'Leer';
}

function formatDate(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  const hm = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return `heute ${hm}`;
  if (isYesterday) return `gestern ${hm}`;
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

/* ── Theme ───────────────────────────────────────────────────────────────── */
function toggleTheme() {
  themeName.value = themeName.value === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = themeName.value;
}

onBeforeUnmount(() => { if (saveTimer) window.clearTimeout(saveTimer); });
</script>

<style scoped>
.dev-harness {
  min-height: 100dvh; display: flex; flex-direction: column;
  background: var(--pm-viewer-surface, #e7eef0);
  color: var(--pm-text, #0e181b);
}

.dev-harness__bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 12px 20px;
  background: var(--pm-app-surface, #fff);
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  flex: none;
}
.dev-harness__brand { display: flex; align-items: center; gap: 12px; }
.dev-harness__mark {
  width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center;
  background: var(--pm-accent, #006b75); color: var(--pm-accent-contrast, #fff);
  font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 13px;
}
.dev-harness__title { font-weight: 600; font-size: 0.95rem; }
.dev-harness__sub {
  font-family: 'IBM Plex Mono', monospace; font-size: 11px;
  color: var(--pm-muted, #535e62); letter-spacing: 0.02em;
}
.dev-btn {
  border: 1px solid var(--pm-divider, #d8dfe1); background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b); border-radius: 8px; padding: 7px 12px;
  font: inherit; font-size: 0.82rem; cursor: pointer;
  transition: border-color 120ms ease, background 120ms ease;
}
.dev-btn:hover { border-color: var(--pm-accent, #006b75); }
.dev-btn--accent { background: var(--pm-accent, #006b75); color: var(--pm-accent-contrast, #fff); border-color: var(--pm-accent, #006b75); }

.dev-harness__body { flex: 1 1 auto; display: grid; grid-template-columns: 264px 1fr; min-height: 0; }

/* ── Liste ───────────────────────────────────────────────────────────────── */
.dev-list {
  border-right: 1px solid var(--pm-divider, #d8dfe1);
  background: var(--pm-app-surface, #fff);
  display: flex; flex-direction: column; min-height: 0; overflow-y: auto;
  padding: 12px;
}
.dev-list__new {
  display: flex; align-items: center; gap: 8px; justify-content: center;
  border: 1px dashed var(--pm-accent, #006b75); background: transparent;
  color: var(--pm-accent-strong, #00555f); border-radius: 10px;
  padding: 10px 12px; font: inherit; font-size: 0.86rem; font-weight: 500; cursor: pointer;
  transition: background 120ms ease;
}
.dev-list__new:hover { background: rgba(var(--v-theme-primary, 0 107 117), 0.08); }
.dev-list__plus { font-size: 1.05rem; line-height: 1; }

.dev-list__empty {
  margin-top: 24px; text-align: center; font-size: 0.82rem;
  color: var(--pm-muted, #535e62); line-height: 1.6;
}

.dev-list__items { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 3px; }
.dev-list__item {
  padding: 10px 11px; border-radius: 10px; cursor: pointer;
  border: 1px solid transparent; transition: background 120ms ease, border-color 120ms ease;
}
.dev-list__item:hover { background: rgba(var(--v-theme-primary, 0 107 117), 0.06); }
.dev-list__item.is-active {
  background: rgba(var(--v-theme-primary, 0 107 117), 0.1);
  border-color: rgba(var(--v-theme-primary, 0 107 117), 0.28);
}
.dev-list__row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.dev-list__name {
  font-size: 0.9rem; font-weight: 500; color: var(--pm-text, #0e181b);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dev-list__del {
  border: 0; background: transparent; color: var(--pm-muted, #535e62);
  cursor: pointer; font-size: 0.78rem; line-height: 1; padding: 3px; border-radius: 6px;
  opacity: 0; transition: opacity 120ms ease, color 120ms ease, background 120ms ease;
}
.dev-list__item:hover .dev-list__del { opacity: 0.7; }
.dev-list__del:hover { opacity: 1; color: #c0392b; background: rgba(192, 57, 43, 0.12); }
.dev-list__meta { margin-top: 2px; }
.dev-list__snippet {
  font-size: 0.76rem; color: var(--pm-muted, #535e62);
  display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dev-list__date {
  margin-top: 4px; font-family: 'IBM Plex Mono', monospace; font-size: 10px;
  color: var(--pm-muted, #535e62); opacity: 0.8;
}

/* ── Editor-Bühne ────────────────────────────────────────────────────────── */
.dev-harness__stage {
  display: flex; justify-content: center; padding: 40px 20px 80px; overflow-y: auto; min-height: 0;
}
.dev-harness__sheet {
  width: 100%; max-width: 760px; align-self: flex-start;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 16px;
  box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.10));
  padding: 44px clamp(24px, 6vw, 64px) 32px;
}
.dev-harness__blank { flex: 1 1 auto; display: grid; place-items: center; }
.dev-harness__blank-inner { text-align: center; color: var(--pm-muted, #535e62); display: grid; gap: 14px; justify-items: center; }
.dev-harness__blank-mark {
  width: 54px; height: 54px; border-radius: 14px; display: grid; place-items: center;
  font-size: 1.5rem; background: var(--pm-app-surface, #fff); border: 1px solid var(--pm-divider, #d8dfe1);
  color: var(--pm-accent, #006b75);
}

@media (max-width: 820px) {
  .dev-harness__body { grid-template-columns: 1fr; }
  .dev-list { flex-direction: row; flex-wrap: nowrap; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--pm-divider, #d8dfe1); }
  .dev-list__items { flex-direction: row; margin: 0 0 0 10px; }
  .dev-list__item { min-width: 180px; }
}
@media (prefers-reduced-motion: reduce) {
  .dev-btn, .dev-list__new, .dev-list__item, .dev-list__del { transition: none; }
}
</style>
