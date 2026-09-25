<template>
  <section class="lernraum-panel">
    <!-- Kein Kurs -->
    <div v-if="!store.courses.length && !store.loadingCourses" class="lr-empty">
      <div class="lr-empty-card">
        <div class="lr-empty-title">Willkommen im Lernraum</div>
        <div class="lr-empty-body">Lege deinen ersten Kurs an – z. B. „Computergrafik 1". Darin sammelst du Lernblätter und lernst später deine Karten.</div>
        <button type="button" class="lr-btn lr-btn--primary lr-btn--md" @click="onCreateCourse">Ersten Kurs anlegen</button>
      </div>
    </div>

    <!-- ============ STARTSEITE ============ -->
    <template v-else-if="view === 'home'">
      <header class="lr-home-head">
        <div class="lr-title-block">
          <span class="lr-title">Lernraum</span>
          <span class="lr-subtitle">{{ store.courses.length }} Kurse · {{ totalSheets }} Lernblätter</span>
        </div>
        <button type="button" class="lr-btn lr-btn--secondary lr-btn--sm" @click="onCreateCourse">Kurs anlegen</button>
      </header>

      <div class="lr-home-body">
        <!-- Offene Nachbereitungen -->
        <section class="lr-section">
          <div class="lr-section-head">
            <span class="lr-overline">Offene Nachbereitungen</span>
            <span class="lr-section-meta" v-if="nachbereitungen.length">{{ nachbereitungen.length }} Kurse · {{ openTotal }} Lernblätter offen</span>
          </div>

          <div v-if="nachbereitungen.length" class="lr-nb-grid">
            <div v-for="c in nachbereitungen" :key="c.id" class="lr-nb-card">
              <div class="lr-nb-top">
                <span class="lr-nb-course">Kurs</span>
                <span class="lr-nb-count">{{ c.open }} offen</span>
              </div>
              <div class="lr-nb-title">{{ c.title }}</div>
              <div class="lr-nb-metaline">{{ c.open }} von {{ c.total }} Lernblättern offen</div>
              <div class="lr-progress">
                <span
                  v-for="(filled, i) in progressSegments(c.total, c.done)"
                  :key="i"
                  class="lr-progress-seg"
                  :class="{ 'lr-progress-seg--on': filled }"
                ></span>
              </div>
              <div class="lr-nb-actions">
                <button type="button" class="lr-btn lr-btn--primary lr-btn--sm" @click="openCourse(c.id)">Öffnen</button>
                <span class="lr-nb-later">Später</span>
              </div>
            </div>
          </div>

          <div v-else class="lr-nb-empty">
            <p>Nichts offen – alle Lernblätter sind auf Stand.</p>
            <p class="lr-nb-empty-hint">Sobald du in Notizen Lernmarker setzt, sammeln sich hier deine offenen Nachbereitungen (kommt mit der Karten-Ebene).</p>
          </div>
        </section>

        <!-- Alle Kurse -->
        <section class="lr-section">
          <div class="lr-section-head">
            <span class="lr-overline">Deine Kurse</span>
          </div>
          <div class="lr-course-chips">
            <button
              v-for="course in store.courses"
              :key="course.id"
              type="button"
              class="lr-course-chip"
              @click="openCourse(course.id)"
            >
              {{ course.title }}<span class="lr-course-chip-count">{{ course.sheet_count }}</span>
            </button>
            <button type="button" class="lr-course-chip lr-course-chip--add" @click="onCreateCourse">+ Kurs</button>
          </div>
        </section>
      </div>
    </template>

    <!-- ============ KURSANSICHT ============ -->
    <template v-else>
      <div class="lr-courses">
        <button type="button" class="lr-back-pill" @click="goHome">← Lernraum</button>
        <span class="lr-courses-sep"></span>
        <button
          v-for="course in store.courses"
          :key="course.id"
          type="button"
          class="lr-course-pill"
          :class="{ 'lr-course-pill--active': course.id === store.activeCourseId }"
          @click="selectCourse(course.id)"
        >
          {{ course.title }}
        </button>
        <button type="button" class="lr-course-pill lr-course-pill--add" @click="onCreateCourse">+ Kurs</button>
      </div>

      <!-- Ein Lernblatt geöffnet -->
      <div v-if="openSheet && !learning" class="lr-sheet-view">
        <button type="button" class="lr-back" @click="openSheetId = null">← Alle Lernblätter</button>
        <div class="lr-sheet-card">
          <div class="lr-sheet-head">
            <div class="lr-sheet-kicker">
              <span class="lr-dot" :style="{ background: dotColor(statusMeta(openSheet.status).dot) }"></span>
              <span class="lr-status-label">{{ statusMeta(openSheet.status).label }}</span>
              <button type="button" class="lr-star lr-star--lg" :class="{ 'lr-star--on': openSheet.is_favorite }" @click="toggleFavorite(openSheet)">{{ openSheet.is_favorite ? '★' : '☆' }}</button>
            </div>
            <h2 class="lr-sheet-title">{{ openSheet.title }}</h2>
            <div class="lr-sheet-meta">
              {{ store.activeCourse.title }}<template v-if="openSheet.sessionTitle"> · {{ openSheet.sessionTitle }}</template><template v-if="openSheet.source_label"> · {{ openSheet.source_label }}</template>
            </div>
          </div>
          <div class="lr-cards-panel">
            <div class="lr-cards-head">
              <span class="lr-cards-title">Karten<span v-if="cards.length" class="lr-cards-num"> · {{ cards.length }}</span></span>
              <div class="lr-cards-head-actions">
                <button type="button" class="lr-btn lr-btn--ghost lr-btn--sm" @click="onAddCard">+ Karte</button>
                <button type="button" class="lr-btn lr-btn--primary lr-btn--sm" :disabled="!cards.length" @click="startLearning">Lernen</button>
              </div>
            </div>

            <div v-if="cards.length" class="lr-card-list">
              <div v-for="(card, i) in cards" :key="card.id" class="lr-card-row">
                <div class="lr-card-row-main">
                  <div class="lr-card-row-top">
                    <span class="lr-kind-chip" :style="kindChipStyle(card.kind)">{{ kindLabel(card.kind) }}</span>
                    <span class="lr-card-row-idx">{{ i + 1 }}</span>
                  </div>
                  <div class="lr-card-front">{{ card.front }}</div>
                  <div v-if="card.back" class="lr-card-back">{{ card.back }}</div>
                  <div v-else class="lr-card-back lr-card-back--empty">— frei formulieren, dann Notiz abgleichen —</div>
                </div>
                <div class="lr-card-row-actions">
                  <button type="button" class="lr-icon-btn" title="Bearbeiten" @click="onEditCard(card)">✎</button>
                  <button type="button" class="lr-icon-btn lr-icon-btn--danger" title="Löschen" @click="onDeleteCard(card)">✕</button>
                </div>
              </div>
            </div>

            <div v-else class="lr-cards-empty">
              <p>Dieses Lernblatt hat noch keine Karten.</p>
              <p class="lr-cards-hint">Lege deine erste Karte an – oder später entstehen sie aus deinen <b>markierten Notizen</b>.</p>
              <button type="button" class="lr-btn lr-btn--secondary lr-btn--sm" @click="onAddCard">Erste Karte anlegen</button>
            </div>
          </div>
          <div class="lr-sheet-foot">
            <div class="lr-foot-status">
              <span class="lr-foot-label">Status</span>
              <div class="lr-status-picker">
                <button v-for="s in statuses" :key="s.value" type="button" class="lr-status-chip" :class="{ 'lr-status-chip--active': openSheet.status === s.value }" @click="setStatus(s.value)">{{ s.label }}</button>
              </div>
            </div>
            <div class="lr-foot-actions">
              <button type="button" class="lr-btn lr-btn--ghost lr-btn--sm" @click="onRenameSheet(openSheet)">Umbenennen</button>
              <button type="button" class="lr-btn lr-btn--ghost lr-btn--sm lr-btn--danger-text" @click="onDeleteSheet(openSheet)">Löschen</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Lernmodus: Karten durchgehen -->
      <div v-else-if="openSheet && learning" class="lr-learn-view">
        <div class="lr-learn-top">
          <button type="button" class="lr-back" @click="exitLearning">← Beenden</button>
          <span class="lr-learn-progress">Karte {{ learnIndex + 1 }} von {{ cards.length }}</span>
        </div>
        <div v-if="currentCard" class="lr-learn-card">
          <span class="lr-kind-chip lr-kind-chip--lg" :style="kindChipStyle(currentCard.kind)">{{ kindLabel(currentCard.kind) }}</span>
          <div class="lr-learn-front">{{ currentCard.front }}</div>
          <div v-if="revealed" class="lr-learn-back">
            <div class="lr-learn-back-label">{{ currentCard.back ? 'Antwort' : 'Zum Abgleich' }}</div>
            <div class="lr-learn-back-text">{{ currentCard.back || 'Diese Karte hat keine Rückseite – formuliere frei und gleiche danach mit deiner Notiz ab.' }}</div>
          </div>
          <div class="lr-learn-actions">
            <button v-if="!revealed" type="button" class="lr-btn lr-btn--primary lr-btn--md" @click="revealed = true">Aufdecken</button>
            <template v-else>
              <button type="button" class="lr-btn lr-btn--ghost lr-btn--md" :disabled="learnIndex === 0" @click="prevCard">Zurück</button>
              <button type="button" class="lr-btn lr-btn--primary lr-btn--md" @click="nextCard">{{ learnIndex + 1 < cards.length ? 'Weiter' : 'Fertig' }}</button>
            </template>
          </div>
        </div>
      </div>

      <!-- Kurs-Übersicht: Lernblätter -->
      <template v-else-if="store.activeCourse">
        <header class="lr-header">
          <div class="lr-title-block">
            <span class="lr-title">{{ store.activeCourse.title }}</span>
            <span class="lr-subtitle">{{ sheetCountLabel }}</span>
          </div>
          <button type="button" class="lr-btn lr-btn--primary lr-btn--md" @click="onCreateSheet">+ Neues Lernblatt</button>
        </header>

        <div class="lr-board">
          <div v-if="!courseSheets.length" class="lr-empty-inline">
            <p>Noch keine Lernblätter in diesem Kurs.</p>
            <p class="lr-empty-inline-hint">Ein Lernblatt bündelt Lernkarten zu einem Thema.</p>
          </div>
          <div v-else class="lr-grid">
            <div
              v-for="sheet in courseSheets"
              :key="sheet.id"
              class="lr-card"
              :class="{ 'lr-card--faded': statusMeta(sheet.status).faded }"
              role="button"
              tabindex="0"
              @click="openSheetId = sheet.id"
              @keydown.enter="openSheetId = sheet.id"
            >
              <div class="lr-card-status">
                <span class="lr-dot" :style="{ background: dotColor(statusMeta(sheet.status).dot) }"></span>
                <span class="lr-status-label">{{ statusMeta(sheet.status).label }}</span>
                <button type="button" class="lr-star" :class="{ 'lr-star--on': sheet.is_favorite }" @click.stop="toggleFavorite(sheet)">{{ sheet.is_favorite ? '★' : '☆' }}</button>
              </div>
              <div class="lr-card-title">{{ sheet.title }}</div>
              <div class="lr-card-foot">
                <span class="lr-card-count">{{ sheet.card_count }} Karten</span>
                <span v-if="sheet.sessionTitle" class="lr-card-session">{{ sheet.sessionTitle }}</span>
              </div>
            </div>
            <button type="button" class="lr-card lr-card--add" @click="onCreateSheet">
              <span class="lr-add-plus">+</span>
              <span>Neues Lernblatt</span>
            </button>
          </div>
        </div>
      </template>
    </template>

    <!-- Anlege-/Bearbeiten-Dialog -->
    <div v-if="dialog" class="lr-modal-scrim" @click.self="closeDialog" @keydown.esc="closeDialog">
      <div class="lr-modal" role="dialog" aria-modal="true">
        <div class="lr-modal-title">{{ dialogTitle }}</div>

        <template v-if="dialog.kind === 'card'">
          <label class="lr-field-label">Typ</label>
          <div class="lr-kind-picker">
            <button
              v-for="k in cardKinds"
              :key="k.value"
              type="button"
              class="lr-kind-opt"
              :class="{ 'lr-kind-opt--on': dialog.cardKind === k.value }"
              @click="dialog.cardKind = k.value"
            >{{ k.label }}</button>
          </div>
          <label class="lr-field-label">Vorderseite <span class="lr-field-opt">Frage / Aufgabe</span></label>
          <textarea class="lr-field lr-field--area" rows="3" v-model="dialog.front" placeholder="Was soll abgefragt werden?"></textarea>
          <label class="lr-field-label">Rückseite <span class="lr-field-opt">Antwort / Lösung – leer lassen für Verständnisfragen</span></label>
          <textarea class="lr-field lr-field--area" rows="3" v-model="dialog.back" placeholder="Antwort … (optional)"></textarea>
        </template>

        <template v-else>
          <label class="lr-field-label">{{ dialog.kind === 'course' ? 'Kursname' : 'Name des Lernblatts' }}</label>
          <input ref="dialogInput" class="lr-field" v-model="dialog.name" @keydown.enter="submitDialog" :placeholder="dialog.kind === 'course' ? 'z. B. Computergrafik 1' : 'z. B. Rasterisierung'" />
        </template>

        <div v-if="dialogError" class="lr-field-error">{{ dialogError }}</div>

        <div class="lr-modal-actions">
          <button type="button" class="lr-btn lr-btn--ghost lr-btn--md" @click="closeDialog">Abbrechen</button>
          <button type="button" class="lr-btn lr-btn--primary lr-btn--md" :disabled="dialogBusy" @click="submitDialog">{{ dialogSubmitLabel }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useLearnStore } from '../stores/learn.js';

// Lernraum: Startseite (Übersicht) → Kurs öffnen → Lernblatt öffnen.
// Rendert INNERHALB der gemeinsamen Shell (echte App-Seitenleiste bleibt stehen).
// „Offene Nachbereitungen" laufen vorerst über den Lernblatt-Status (draft/in_progress),
// bis die Marker-/Karten-Ebene (Maske 1b) echte Marker liefert.

const store = useLearnStore();

const view = ref('home'); // 'home' | 'course'
const openSheetId = ref(null);

const totalSheets = computed(() => store.courses.reduce((n, c) => n + (c.sheet_count || 0), 0));

// Lernblätter des aktiven Kurses (mit Sitzungstitel als Etikett).
const courseSheets = computed(() => {
  const board = store.board;
  if (!board) return [];
  const rows = [];
  for (const s of board.sessions || []) for (const sheet of s.sheets) rows.push({ ...sheet, sessionTitle: s.title });
  for (const sheet of board.loose_sheets || []) rows.push({ ...sheet, sessionTitle: null });
  return rows;
});
const openSheet = computed(() => courseSheets.value.find((s) => s.id === openSheetId.value) || null);

// --- Karten des offenen Lernblatts ---
const cards = computed(() => (store.cardsSheetId === openSheetId.value ? store.cards : []));

const KIND = {
  fakt: { label: 'Fakt', tint: 'success' },
  prozess: { label: 'Prozess', tint: 'accent' },
  zusammenhang: { label: 'Vergleich', tint: 'accent' },
  prozedural: { label: 'Anleitung', tint: 'neutral' },
  verstaendnis: { label: 'Verständnis', tint: 'accent' },
  uebung: { label: 'Übung', tint: 'warning' },
};
function kindLabel(kind) { return (KIND[kind] || KIND.fakt).label; }
function kindChipStyle(kind) {
  const tint = (KIND[kind] || KIND.fakt).tint;
  if (tint === 'success') return { background: 'color-mix(in oklab, var(--pm-success) 16%, transparent)', color: 'var(--pm-success)' };
  if (tint === 'warning') return { background: 'color-mix(in oklab, var(--pm-star) 18%, transparent)', color: 'var(--pm-star)' };
  if (tint === 'accent') return { background: 'var(--pm-selected)', color: 'var(--pm-accent-text)' };
  return { background: 'var(--pm-chip-bg)', color: 'var(--pm-chip-text)' };
}

// --- Lernmodus ---
const learning = ref(false);
const learnIndex = ref(0);
const revealed = ref(false);
const currentCard = computed(() => cards.value[learnIndex.value] || null);
function startLearning() {
  if (!cards.value.length) return;
  learnIndex.value = 0;
  revealed.value = false;
  learning.value = true;
}
function exitLearning() { learning.value = false; }
function nextCard() {
  if (learnIndex.value + 1 < cards.value.length) {
    learnIndex.value += 1;
    revealed.value = false;
  } else {
    learning.value = false;
  }
}
function prevCard() {
  if (learnIndex.value > 0) {
    learnIndex.value -= 1;
    revealed.value = false;
  }
}

const sheetCountLabel = computed(() => {
  const n = courseSheets.value.length;
  return n === 1 ? '1 Lernblatt' : `${n} Lernblätter`;
});

// Startseite: pro Kurs offene (nicht „gelernte") Lernblätter.
const OPEN_STATUS = new Set(['draft', 'in_progress']);
const nachbereitungen = computed(() => {
  const byCourse = new Map();
  for (const sheet of store.allSheets || []) {
    if (sheet.status === 'archived') continue;
    const e = byCourse.get(sheet.course_id) || { total: 0, done: 0, open: 0 };
    e.total += 1;
    if (sheet.status === 'worked') e.done += 1;
    if (OPEN_STATUS.has(sheet.status)) e.open += 1;
    byCourse.set(sheet.course_id, e);
  }
  return store.courses
    .map((c) => ({ id: c.id, title: c.title, ...(byCourse.get(c.id) || { total: 0, done: 0, open: 0 }) }))
    .filter((c) => c.open > 0)
    .sort((a, b) => b.open - a.open);
});
const openTotal = computed(() => nachbereitungen.value.reduce((n, c) => n + c.open, 0));

function progressSegments(total, done) {
  const n = Math.max(1, Math.min(total || 0, 8));
  const filled = total > 0 ? Math.round((done / total) * n) : 0;
  return Array.from({ length: n }, (_, i) => i < filled);
}

watch(() => store.board, () => {
  if (openSheetId.value && !openSheet.value) openSheetId.value = null;
});

const STATUS = {
  in_progress: { label: 'In Arbeit', dot: 'accent' },
  draft: { label: 'Entwurf', dot: 'border' },
  worked: { label: 'Gelernt', dot: 'success' },
  archived: { label: 'Abgelegt', dot: 'border', faded: true },
};
const statuses = [
  { value: 'draft', label: 'Entwurf' },
  { value: 'in_progress', label: 'In Arbeit' },
  { value: 'worked', label: 'Gelernt' },
  { value: 'archived', label: 'Abgelegt' },
];
function statusMeta(status) { return STATUS[status] || STATUS.draft; }
function dotColor(kind) {
  if (kind === 'accent') return 'var(--pm-accent)';
  if (kind === 'success') return 'var(--pm-success)';
  return 'var(--pm-border)';
}

function goHome() { view.value = 'home'; openSheetId.value = null; store.fetchAllSheets(); }
function openCourse(id) { openSheetId.value = null; view.value = 'course'; store.selectCourse(id); }
function selectCourse(id) { openSheetId.value = null; store.selectCourse(id); }

function onCreateCourse() { openDialog({ kind: 'course', name: '' }); }
function onCreateSheet() {
  if (!store.activeCourseId) return;
  openDialog({ kind: 'sheet', name: '' });
}
async function toggleFavorite(sheet) { await store.patchSheet(sheet.id, { is_favorite: !sheet.is_favorite }); }
async function setStatus(status) {
  if (!openSheet.value || openSheet.value.status === status) return;
  await store.patchSheet(openSheet.value.id, { status });
}
function onRenameSheet(sheet) { openDialog({ kind: 'sheet-rename', sheetId: sheet.id, name: sheet.title }); }
async function onDeleteSheet(sheet) {
  if (!window.confirm(`„${sheet.title}" löschen?`)) return;
  await store.removeSheet(sheet.id);
  openSheetId.value = null;
}

// Karten des offenen Blatts laden; Lernmodus beim Blattwechsel verlassen.
watch(openSheetId, (id) => {
  learning.value = false;
  if (id) store.fetchCards(id);
}, { immediate: true });

const DEFAULT_KIND = 'fakt';
function onAddCard() {
  if (!openSheetId.value) return;
  openDialog({ kind: 'card', cardId: null, cardKind: store.activeCourse?.default_artifact_type || DEFAULT_KIND, front: '', back: '' });
}
function onEditCard(card) {
  openDialog({ kind: 'card', cardId: card.id, cardKind: card.kind, front: card.front, back: card.back || '' });
}
async function onDeleteCard(card) {
  if (!window.confirm('Karte löschen?')) return;
  await store.removeCard(card.id, openSheetId.value);
}

// --- Anlege-/Bearbeiten-Dialog ---
const dialog = ref(null);
const dialogError = ref('');
const dialogBusy = ref(false);
const dialogInput = ref(null);
const cardKinds = [
  { value: 'fakt', label: 'Fakt' },
  { value: 'verstaendnis', label: 'Verständnis' },
  { value: 'uebung', label: 'Übung' },
  { value: 'prozess', label: 'Prozess' },
  { value: 'zusammenhang', label: 'Vergleich' },
  { value: 'prozedural', label: 'Anleitung' },
];
const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return '';
  if (d.kind === 'card') return d.cardId ? 'Karte bearbeiten' : 'Neue Karte';
  if (d.kind === 'course') return 'Neuer Kurs';
  if (d.kind === 'sheet') return 'Neues Lernblatt';
  if (d.kind === 'sheet-rename') return 'Lernblatt umbenennen';
  return '';
});
const dialogSubmitLabel = computed(() => {
  const d = dialog.value;
  return d && ((d.kind === 'card' && d.cardId) || d.kind === 'sheet-rename') ? 'Speichern' : 'Anlegen';
});
function openDialog(shape) {
  dialogError.value = '';
  dialog.value = shape;
  nextTick(() => { try { dialogInput.value?.focus(); } catch { /* Fokus ist optional */ } });
}
function closeDialog() { dialog.value = null; dialogError.value = ''; }
async function submitDialog() {
  const d = dialog.value;
  if (!d || dialogBusy.value) return;
  dialogBusy.value = true;
  try {
    if (d.kind === 'card') {
      if (!d.front.trim()) { dialogError.value = 'Bitte eine Vorderseite eingeben.'; return; }
      const payload = { kind: d.cardKind, front: d.front.trim(), back: d.back.trim() || null };
      if (d.cardId) await store.patchCard(d.cardId, openSheetId.value, payload);
      else await store.addCard(openSheetId.value, payload);
    } else {
      if (!d.name.trim()) { dialogError.value = 'Bitte einen Namen eingeben.'; return; }
      if (d.kind === 'course') { await store.addCourse({ title: d.name.trim() }); view.value = 'course'; }
      else if (d.kind === 'sheet') await store.addSheet({ course_id: store.activeCourseId, title: d.name.trim(), scope: 'topic' });
      else if (d.kind === 'sheet-rename') await store.patchSheet(d.sheetId, { title: d.name.trim() });
    }
    dialog.value = null;
  } catch (err) {
    dialogError.value = err?.message || 'Aktion fehlgeschlagen.';
  } finally {
    dialogBusy.value = false;
  }
}

onMounted(() => {
  store.fetchCourses();
  store.fetchAllSheets();
});
</script>

<style>
.lernraum-panel {
  --pm-font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  --pm-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  --pm-bg: #ffffff;
  --pm-surface-card: #ffffff;
  --pm-surface-reader: oklch(0.968 0.006 210);
  --pm-border: oklch(0.900 0.008 210);
  --pm-text: oklch(0.200 0.015 220);
  --pm-text-muted: oklch(0.475 0.015 220);
  --pm-accent: oklch(0.475 0.095 205);
  --pm-accent-text: oklch(0.400 0.090 205);
  --pm-on-accent: #ffffff;
  --pm-selected: oklch(0.948 0.026 205);
  --pm-chip-bg: oklch(0.945 0.008 210);
  --pm-chip-text: oklch(0.320 0.015 220);
  --pm-chip-count: oklch(0.560 0.014 220);
  --pm-track: oklch(0.930 0.008 210);
  --pm-star: oklch(0.630 0.130 72);
  --pm-success: oklch(0.490 0.100 150);
  --pm-danger: oklch(0.520 0.150 27);
  position: relative;
  min-width: 0; height: 100%; min-height: 0; display: flex; flex-direction: column;
  overflow: hidden; background: var(--pm-surface-reader); color: var(--pm-text); font-family: var(--pm-font-sans);
}
:root[data-theme="dark"] .lernraum-panel {
  --pm-bg: oklch(0.275 0.014 222);
  --pm-surface-card: oklch(0.345 0.012 222);
  --pm-surface-reader: oklch(0.250 0.014 222);
  --pm-border: oklch(0.395 0.014 222);
  --pm-text: oklch(0.965 0.005 220);
  --pm-text-muted: oklch(0.760 0.014 220);
  --pm-accent: oklch(0.760 0.105 200);
  --pm-accent-text: oklch(0.845 0.090 200);
  --pm-on-accent: oklch(0.200 0.030 200);
  --pm-selected: oklch(0.375 0.050 205);
  --pm-chip-bg: oklch(0.395 0.014 222);
  --pm-chip-text: oklch(0.945 0.006 220);
  --pm-chip-count: oklch(0.775 0.014 220);
  --pm-track: oklch(0.375 0.014 222);
  --pm-star: oklch(0.800 0.130 72);
  --pm-success: oklch(0.760 0.105 150);
  --pm-danger: oklch(0.720 0.140 27);
}

/* Buttons */
.lernraum-panel .lr-btn { border: 0; cursor: pointer; font-family: var(--pm-font-sans); border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; }
.lernraum-panel .lr-btn--primary { background: var(--pm-accent); color: var(--pm-on-accent); font-weight: 620; }
.lernraum-panel .lr-btn--primary:hover:not([disabled]) { filter: brightness(1.06); }
.lernraum-panel .lr-btn--secondary { background: var(--pm-bg); border: 1px solid var(--pm-border); color: var(--pm-text); }
.lernraum-panel .lr-btn--secondary:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-btn--ghost { background: transparent; border: 1px solid var(--pm-border); color: var(--pm-text-muted); }
.lernraum-panel .lr-btn--ghost:hover { background: var(--pm-surface-reader); color: var(--pm-text); }
.lernraum-panel .lr-btn--danger-text { color: var(--pm-danger); }
.lernraum-panel .lr-btn--sm { height: 30px; padding: 0 13px; font-size: 12.5px; }
.lernraum-panel .lr-btn--md { height: 36px; padding: 0 18px; font-size: 13.5px; }
.lernraum-panel .lr-btn[disabled] { opacity: .45; cursor: default; }

/* Titelblöcke */
.lernraum-panel .lr-title-block { display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-title { font: 660 24px/1.2 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-subtitle { font-size: 13px; color: var(--pm-text-muted); }

/* Startseite */
.lernraum-panel .lr-home-head { flex: none; display: flex; align-items: center; gap: 16px; padding: 22px 40px 16px; background: var(--pm-bg); border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-home-head .lr-btn { margin-left: auto; }
.lernraum-panel .lr-home-body { flex: 1; min-height: 0; overflow: auto; padding: 26px 40px 32px; display: flex; flex-direction: column; gap: 30px; }
.lernraum-panel .lr-section { display: flex; flex-direction: column; gap: 14px; }
.lernraum-panel .lr-section-head { display: flex; align-items: baseline; gap: 12px; }
.lernraum-panel .lr-overline { font: 620 11.5px/1.4 var(--pm-font-sans); letter-spacing: .09em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-section-meta { font-size: 12.5px; color: var(--pm-text-muted); }

.lernraum-panel .lr-nb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px; }
.lernraum-panel .lr-nb-card { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); padding: 18px 20px; display: flex; flex-direction: column; gap: 11px; }
.lernraum-panel .lr-nb-top { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-nb-course { font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-nb-count { margin-left: auto; font-size: 11.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-nb-title { font: 620 15.5px/1.3 var(--pm-font-sans); letter-spacing: -.015em; text-wrap: pretty; }
.lernraum-panel .lr-nb-metaline { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-progress { display: flex; gap: 4px; margin-top: 2px; }
.lernraum-panel .lr-progress-seg { flex: 1; height: 4px; border-radius: 2px; background: var(--pm-track); }
.lernraum-panel .lr-progress-seg--on { background: var(--pm-accent); }
.lernraum-panel .lr-nb-actions { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.lernraum-panel .lr-nb-later { font-size: 12px; color: var(--pm-text-muted); cursor: default; }

.lernraum-panel .lr-nb-empty { border: 1px dashed var(--pm-border); border-radius: 14px; padding: 22px; }
.lernraum-panel .lr-nb-empty p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-nb-empty .lr-nb-empty-hint { margin-top: 6px; font-size: 12.5px; color: var(--pm-text-muted); line-height: 1.55; }

.lernraum-panel .lr-course-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.lernraum-panel .lr-course-chip { height: 34px; display: inline-flex; align-items: center; gap: 8px; padding: 0 15px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-surface-card); color: var(--pm-text); font: 520 13.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-course-chip:hover { border-color: var(--pm-accent); }
.lernraum-panel .lr-course-chip-count { font-size: 12px; color: var(--pm-chip-count); }
.lernraum-panel .lr-course-chip--add { color: var(--pm-text-muted); border-style: dashed; }

/* Kursleiste (Kursansicht) */
.lernraum-panel .lr-courses { flex: none; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 12px 28px; background: var(--pm-bg); border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-back-pill { height: 32px; display: inline-flex; align-items: center; padding: 0 13px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text-muted); font: 520 13px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-back-pill:hover { background: var(--pm-surface-reader); color: var(--pm-text); }
.lernraum-panel .lr-courses-sep { width: 1px; height: 20px; background: var(--pm-border); margin: 0 4px; }
.lernraum-panel .lr-course-pill { height: 32px; display: inline-flex; align-items: center; padding: 0 15px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text); font: 520 13.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-course-pill:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-course-pill--active { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-course-pill--add { color: var(--pm-text-muted); border-style: dashed; }

/* Kurs-Kopf + Board */
.lernraum-panel .lr-header { flex: none; display: flex; align-items: center; gap: 16px; padding: 20px 28px 16px; }
.lernraum-panel .lr-header .lr-btn--primary { margin-left: auto; }
.lernraum-panel .lr-board { flex: 1; min-height: 0; overflow: auto; padding: 4px 28px 28px; }
.lernraum-panel .lr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 16px; }
.lernraum-panel .lr-card { display: flex; flex-direction: column; gap: 12px; padding: 16px; min-height: 132px; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); text-align: left; color: var(--pm-text); font-family: var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-card:hover { border-color: var(--pm-accent); box-shadow: 0 2px 10px rgba(0,0,0,.05); }
.lernraum-panel .lr-card--faded { opacity: .55; }
.lernraum-panel .lr-card--add { align-items: center; justify-content: center; gap: 6px; border-style: dashed; color: var(--pm-text-muted); font-size: 13px; text-align: center; }
.lernraum-panel .lr-card--add:hover { background: var(--pm-bg); color: var(--pm-accent-text); border-color: var(--pm-accent); box-shadow: none; }
.lernraum-panel .lr-add-plus { font-size: 22px; line-height: 1; }
.lernraum-panel .lr-card-status { display: flex; align-items: center; gap: 6px; }
.lernraum-panel .lr-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.lernraum-panel .lr-status-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .07em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-star { margin-left: auto; color: var(--pm-border); font-size: 14px; background: transparent; border: 0; cursor: pointer; line-height: 1; padding: 0; }
.lernraum-panel .lr-star--lg { font-size: 18px; }
.lernraum-panel .lr-star--on { color: var(--pm-star); }
.lernraum-panel .lr-card-title { font: 620 16px/1.3 var(--pm-font-sans); letter-spacing: -.01em; text-wrap: pretty; flex: 1; }
.lernraum-panel .lr-card-foot { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.lernraum-panel .lr-card-count { font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-card-session { font-size: 11.5px; color: var(--pm-chip-text); background: var(--pm-chip-bg); padding: 2px 8px; border-radius: 20px; }

/* Lernblatt-Seite */
.lernraum-panel .lr-sheet-view { flex: 1; min-height: 0; overflow: auto; padding: 18px 28px 32px; }
.lernraum-panel .lr-back { background: 0; border: 0; padding: 6px 0; color: var(--pm-text-muted); font: 520 13px/1 var(--pm-font-sans); cursor: pointer; margin-bottom: 12px; }
.lernraum-panel .lr-back:hover { color: var(--pm-text); }
.lernraum-panel .lr-sheet-card { max-width: 760px; display: flex; flex-direction: column; gap: 22px; }
.lernraum-panel .lr-sheet-head { display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-sheet-kicker { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-sheet-title { margin: 0; font: 660 26px/1.2 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-sheet-meta { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-cards-panel { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); overflow: hidden; }
.lernraum-panel .lr-cards-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-cards-title { font: 620 14px/1.3 var(--pm-font-sans); }
.lernraum-panel .lr-cards-empty { padding: 28px 18px; text-align: center; }
.lernraum-panel .lr-cards-empty p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-cards-empty .lr-cards-hint { margin-top: 6px; margin-bottom: 14px; font-size: 12.5px; color: var(--pm-text-muted); }
.lernraum-panel .lr-cards-num { color: var(--pm-text-muted); font-weight: 520; }
.lernraum-panel .lr-cards-head-actions { display: flex; gap: 8px; }

/* Karten-Liste */
.lernraum-panel .lr-card-list { display: flex; flex-direction: column; }
.lernraum-panel .lr-card-row { display: flex; gap: 12px; padding: 14px 18px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-card-row:first-child { border-top: 0; }
.lernraum-panel .lr-card-row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.lernraum-panel .lr-card-row-top { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-card-row-idx { font-size: 11.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-kind-chip { display: inline-flex; align-items: center; height: 19px; padding: 0 8px; border-radius: 20px; font: 620 10.5px/1 var(--pm-font-sans); letter-spacing: .05em; text-transform: uppercase; }
.lernraum-panel .lr-kind-chip--lg { height: 24px; padding: 0 11px; font-size: 12px; }
.lernraum-panel .lr-card-front { font: 520 14px/1.5 var(--pm-font-sans); color: var(--pm-text); }
.lernraum-panel .lr-card-back { font-size: 13px; line-height: 1.5; color: var(--pm-text-muted); }
.lernraum-panel .lr-card-back--empty { font-style: italic; opacity: .8; }
.lernraum-panel .lr-card-row-actions { display: flex; gap: 4px; align-items: flex-start; }
.lernraum-panel .lr-icon-btn { width: 26px; height: 26px; border: 0; border-radius: 6px; background: transparent; color: var(--pm-text-muted); cursor: pointer; font-size: 13px; line-height: 1; }
.lernraum-panel .lr-icon-btn:hover { background: var(--pm-surface-reader); color: var(--pm-text); }
.lernraum-panel .lr-icon-btn--danger:hover { color: var(--pm-danger); }

/* Lernmodus */
.lernraum-panel .lr-learn-view { flex: 1; min-height: 0; overflow: auto; padding: 18px 28px 32px; display: flex; flex-direction: column; }
.lernraum-panel .lr-learn-top { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.lernraum-panel .lr-learn-progress { font-size: 12.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-learn-card { max-width: 640px; width: 100%; margin: 8px auto 0; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); padding: 28px 30px; display: flex; flex-direction: column; gap: 18px; }
.lernraum-panel .lr-learn-card .lr-kind-chip { align-self: flex-start; }
.lernraum-panel .lr-learn-front { font: 620 20px/1.4 var(--pm-font-sans); letter-spacing: -.01em; color: var(--pm-text); text-wrap: pretty; }
.lernraum-panel .lr-learn-back { border-top: 1px solid var(--pm-border); padding-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.lernraum-panel .lr-learn-back-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .08em; text-transform: uppercase; color: var(--pm-accent-text); }
.lernraum-panel .lr-learn-back-text { font: 400 16px/1.6 var(--pm-font-sans); color: var(--pm-text); text-wrap: pretty; }
.lernraum-panel .lr-learn-actions { display: flex; gap: 10px; margin-top: 4px; }

.lernraum-panel .lr-sheet-foot { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; flex-wrap: wrap; padding-top: 16px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-foot-status { display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-foot-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .07em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-status-picker { display: flex; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-status-chip { height: 30px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text-muted); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-status-chip:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-status-chip--active { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-foot-actions { display: flex; gap: 8px; }

/* Leerzustände */
.lernraum-panel .lr-empty { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; }
.lernraum-panel .lr-empty-card { max-width: 440px; text-align: center; display: flex; flex-direction: column; gap: 14px; align-items: center; padding: 36px; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); }
.lernraum-panel .lr-empty-title { font: 660 20px/1.25 var(--pm-font-sans); letter-spacing: -.015em; }
.lernraum-panel .lr-empty-body { font-size: 14px; line-height: 1.6; color: var(--pm-text-muted); }
.lernraum-panel .lr-empty-inline { padding: 24px 0; }
.lernraum-panel .lr-empty-inline p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-empty-inline .lr-empty-inline-hint { margin-top: 5px; font-size: 12.5px; color: var(--pm-text-muted); }

/* Dialog */
.lernraum-panel .lr-modal-scrim { position: absolute; inset: 0; z-index: 20; background: color-mix(in oklab, #000 42%, transparent); display: flex; align-items: center; justify-content: center; padding: 24px; }
.lernraum-panel .lr-modal { width: 100%; max-width: 480px; max-height: 100%; overflow: auto; background: var(--pm-bg); border: 1px solid var(--pm-border); border-radius: 16px; box-shadow: 0 16px 48px rgba(0,0,0,.28); padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 12px; }
.lernraum-panel .lr-modal-title { font: 660 18px/1.25 var(--pm-font-sans); letter-spacing: -.015em; margin-bottom: 2px; }
.lernraum-panel .lr-field-label { font: 620 11.5px/1.4 var(--pm-font-sans); letter-spacing: .06em; text-transform: uppercase; color: var(--pm-text-muted); margin-top: 4px; }
.lernraum-panel .lr-field-opt { text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--pm-text-muted); opacity: .85; }
.lernraum-panel .lr-field { width: 100%; border: 1px solid var(--pm-border); border-radius: 9px; background: var(--pm-surface-card); color: var(--pm-text); font: 400 14px/1.5 var(--pm-font-sans); padding: 9px 11px; outline: none; }
.lernraum-panel .lr-field:focus { border-color: var(--pm-accent); box-shadow: 0 0 0 3px var(--pm-selected); }
.lernraum-panel .lr-field--area { resize: vertical; min-height: 60px; }
.lernraum-panel .lr-kind-picker { display: flex; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-kind-opt { height: 30px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-surface-card); color: var(--pm-text-muted); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-kind-opt:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-kind-opt--on { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-field-error { font-size: 12.5px; color: var(--pm-danger); }
.lernraum-panel .lr-modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
</style>
