<!--
  Detail-Panel der KI-Überarbeitung (Design-Variante 2B). Angedockte Spalte
  rechts vom Editor. Flache, in Lesereihenfolge nummerierte Kartenliste; die
  Ziffer im Badge entspricht der hochgestellten Ziffer am Anker im Text. Aktionen
  erscheinen nur auf der fokussierten Karte. Es wird nie in die Notiz geschrieben,
  bis „Übernehmen" (Fußzeile) geklickt wird – dann als ein einziger Undo-Schritt.
-->
<template>
  <aside class="pm-review-panel" role="dialog" aria-label="KI-Überarbeitung · Verbesserungen" @keydown.esc.stop="clearFocus">
    <header class="pm-review-panel__head">
      <span class="pm-review-panel__rubric" aria-live="polite">{{ headRubric }}</span>
      <button
        type="button"
        class="pm-review-panel__marks"
        :class="{ 'is-on': review.showMarks }"
        :aria-pressed="review.showMarks ? 'true' : 'false'"
        :title="review.showMarks ? 'Markierungen im Text ausblenden' : 'Markierungen im Text einblenden'"
        @click="toggleMarks"
      >
        <v-icon size="16">{{ review.showMarks ? 'mdi-eye' : 'mdi-eye-off' }}</v-icon>
      </button>
    </header>

    <!-- Sortieren + Filtern (Offen/Abgelehnt) – identisch zur Notizenliste. -->
    <ListActionToolbar
      v-if="!review.loading && !review.error && !review.empty && review.changes.length"
      :actions="toolbarActions"
      :show-selection="false"
      @action-select="onToolbarAction"
    />

    <!-- Prüfung läuft – animierte Standard-Platzhalter (wie in der Dokumentenliste). -->
    <div v-if="review.loading" class="pm-review-panel__body">
      <v-skeleton-loader
        v-for="n in 3"
        :key="`rev-skel-${n}`"
        type="list-item-avatar-two-line"
        class="pm-review-skeleton"
      />

    </div>

    <div v-else class="pm-review-panel__body" @click.self="clearFocus">
      <div v-if="review.error" class="pm-review-panel__placeholder pm-review-panel__placeholder--error" role="alert">
        <PmEmptyState
          icon="mdi-alert-circle-outline"
          title="Prüfung nicht abgeschlossen"
          :subtitle="review.error"
          size="sm"
          :animated="false"
        >
          <button type="button" class="pm-review-panel__ghost" @click="regenerateReview">
            <v-icon size="16">mdi-refresh</v-icon>
            Erneut prüfen
          </button>
        </PmEmptyState>
      </div>

      <div v-else-if="review.empty" class="pm-review-panel__placeholder" role="status">
        <PmEmptyState
          :icon="review.stale ? 'mdi-refresh' : 'mdi-check-circle-outline'"
          :title="review.stale ? 'Text geändert' : 'Keine Verbesserungen gefunden'"
          :subtitle="review.stale ? 'Prüfe die aktuelle Fassung, um neue Verbesserungsvorschläge zu erhalten.' : 'Für diesen Text liegen keine weiteren Vorschläge vor.'"
          size="sm"
        >
          <button type="button" class="pm-review-panel__ghost" @click="regenerateReview">
            <v-icon size="16">mdi-refresh</v-icon>
            Erneut prüfen
          </button>
        </PmEmptyState>
      </div>

      <template v-else>
        <p v-if="review.stale" class="pm-review-panel__changed" role="status">Text geändert. Vorschläge zu unveränderten Abschnitten bleiben erhalten.</p>
        <!-- Abschnitte „Offen"/„Abgelehnt"; Abschnittsköpfe nur im Filter „Alle". -->
        <template v-for="section in reviewSections" :key="section.key">
          <div
            v-if="review.filter === 'all' && section.cards.length"
            class="pm-review-section-head"
          >{{ section.label }}<span class="pm-review-section-head__count">{{ section.cards.length }}</span></div>
          <article
            v-for="change in section.cards"
            :key="change.id"
            class="pm-review-card"
            :class="[
              `pm-review-card--${change.cat}`,
              { 'is-focus': effectiveFocusId === change.id, 'is-rejected': review.status[change.id] === 'rejected' },
            ]"
            :data-review-id="change.id"
            @click="revealChange(change.id)"
          >
            <span
              class="pm-review-badge"
              :class="`pm-review-badge--${change.cat}`"
              aria-hidden="true"
            >{{ change.number }} {{ meta(change.cat).glyph }}</span>
            <div class="pm-review-card__main">
              <div class="pm-review-card__header">
                <div class="pm-review-card__title">
                  {{ meta(change.cat).label }}
                  <span
                    v-if="change.cat === 'add' && change.confidence"
                    class="pm-review-conf"
                    :class="{ 'is-low': change.confidence === 'niedrig' }"
                  >· {{ confidenceLabel(change.confidence) }}</span>
                </div>
                <button
                  v-if="effectiveFocusId === change.id"
                  type="button"
                  class="pm-review-card__preview-toggle"
                  :aria-expanded="expandedPreview === change.id"
                  :aria-controls="`review-preview-${change.id}`"
                  @click.stop="expandedPreview = expandedPreview === change.id ? null : change.id"
                >
                  Vorschau
                  <v-icon class="pm-review-card__preview-chevron" size="16" aria-hidden="true">mdi-chevron-down</v-icon>
                </button>
              </div>
              <div class="pm-review-card__summary">{{ change.summary }}</div>
              <NoteReviewPreview v-if="effectiveFocusId === change.id && expandedPreview === change.id" :id="`review-preview-${change.id}`" class="pm-review-card__after" :text="change.revised" :structured="Boolean(change.blockIds?.length)" />
              <Transition name="pm-review-actions">
                <div v-if="effectiveFocusId === change.id" class="pm-review-card__actions">
                  <button type="button" class="is-accent" @click.stop="animateDecision($event, change.id, 'accept')">Annehmen</button>
                  <button
                    v-if="review.status[change.id] === 'rejected'"
                    type="button"
                    @click.stop="reopenChange(change.id)"
                  >Zurücknehmen</button>
                  <button v-else type="button" @click.stop="animateDecision($event, change.id, 'reject')">Ablehnen</button>
                </div>
              </Transition>
            </div>
          </article>
        </template>

        <!-- Leerer Filterzustand -->
        <div v-if="!reviewCards.length" class="pm-review-panel__placeholder" role="status">
          <PmEmptyState
            icon="mdi-check-circle-outline"
            :title="review.filter === 'rejected' ? 'Nichts abgelehnt' : 'Alle Verbesserungen bearbeitet'"
            :subtitle="review.filter === 'rejected'
              ? 'Abgelehnte Verbesserungen erscheinen hier.'
              : 'Es sind keine offenen Verbesserungen mehr übrig.'"
            size="sm"
          />
        </div>

        <div v-if="review.instructionOpen" class="pm-review-panel__instruction">
          <input
            v-model="review.instruction"
            type="text"
            maxlength="600"
            placeholder="Zusätzliche Anweisung … (z. B. „förmlicher“)"
            aria-label="Zusätzliche Anweisung"
            @keydown.enter.prevent="regenerateReview"
          />
          <button type="button" :disabled="review.loading" @click="regenerateReview">Anwenden</button>
        </div>
      </template>
    </div>

    <footer class="pm-review-panel__footer">
      <div class="pm-review-panel__footer-secondary">
        <button
          v-if="!review.loading && review.changes.length"
          type="button"
          class="is-quiet"
          @click="regenerateReview"
        ><v-icon size="16">mdi-refresh</v-icon> Neu</button>
        <button
          v-if="!review.loading && review.changes.length"
          type="button"
          class="is-quiet"
          @click="review.instructionOpen = !review.instructionOpen"
        ><v-icon size="16">mdi-message-text-outline</v-icon> Anweisung</button>
      </div>
      <div class="pm-review-panel__footer-primary">
        <button type="button" class="is-apply" @click="closeReview()">
          <v-icon size="16">mdi-check</v-icon> Fertig
        </button>
      </div>
    </footer>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import PmEmptyState from '../PmEmptyState.vue';
import NoteReviewPreview from './NoteReviewPreview.vue';
import ListActionToolbar from '../ListActionToolbar.vue';
import { REVIEW_CATEGORY_META, REVIEW_CONFIDENCE_LABEL } from './composables/noteReviewLabels.js';

const REVIEW_SORT_OPTIONS = [
  { value: 'order', label: 'Reihenfolge' },
  { value: 'type', label: 'Typ' },
];

const expandedPreview = ref(null);
const props = defineProps({ controller: { type: Object, required: true } });
const {
  review,
  effectiveFocusId,
  reviewCards,
  reviewSections,
  openCount,
  rejectedCount,
  acceptChange,
  rejectChange,
  reopenChange,
  setFilter,
  revealChange,
  clearFocus,
  toggleMarks,
  setSort,
  regenerateReview,
  closeReview,
} = props.controller;

watch(effectiveFocusId, () => { expandedPreview.value = null; });

// Die Entscheidung gilt sofort. Nur eine nicht interaktive Kopie animiert
// aus der Liste, damit Schließen oder Notizwechsel keine Aktion verschluckt.
const decisionAnimations = new Set();
function animateDecision(event, id, kind) {
  const card = event.currentTarget.closest('.pm-review-card');
  const panel = card?.closest('.pm-review-panel');
  const body = card?.closest('.pm-review-panel__body');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    || document.querySelector('.pm-no-animations');
  const positions = new Map();
  if (card && panel && !reduced && typeof card.animate === 'function') {
    body?.querySelectorAll('.pm-review-card').forEach(el => positions.set(el, el.getBoundingClientRect().top));
    const rect = card.getBoundingClientRect();
    const ghost = card.cloneNode(true);
    ghost.classList.add('pm-review-card--decision', `is-${kind === 'accept' ? 'accepted' : 'dismissed'}`);
    ghost.setAttribute('aria-hidden', 'true');
    ghost.inert = true;
    ghost.removeAttribute('data-review-id');
    ghost.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
    Object.assign(ghost.style, {
      position: 'fixed', top: `${rect.top}px`, left: `${rect.left}px`,
      width: `${rect.width}px`, height: `${rect.height}px`, margin: '0',
      boxSizing: 'border-box', zIndex: '20', pointerEvents: 'none',
      transformOrigin: '50% 0',
    });
    const badge = ghost.querySelector('.pm-review-badge');
    if (badge) badge.textContent = kind === 'accept' ? '✓' : '−';
    panel.append(ghost);
    const frames = [
          { opacity: 1, transform: 'translateY(0) scale(1)', boxShadow: '0 0 0 0 transparent' },
          { opacity: 1, transform: 'translateY(2px) scale(0.97, 0.94)', offset: 0.18 },
          { opacity: 1, transform: 'translateY(-7px) scale(1.035, 1.025)',
            boxShadow: '0 0 0 6px color-mix(in srgb, var(--pm-review-decision-color) 20%, transparent), 0 14px 30px color-mix(in srgb, var(--pm-review-decision-color) 22%, transparent)', offset: 0.43 },
          { opacity: 1, transform: 'translateY(-3px) scale(1)', offset: 0.58 },
          { opacity: 1, transform: 'translateY(0) scale(1)', boxShadow: '0 0 0 0 transparent' },
        ];
    const animation = ghost.animate(frames, { duration: 420, easing: 'ease-in-out', fill: 'forwards' });
    const cleanup = () => { animation.cancel(); ghost.remove(); decisionAnimations.delete(cleanup); };
    decisionAnimations.add(cleanup);
    animation.finished.then(cleanup, cleanup);
  }
  if (kind === 'accept') acceptChange(id);
  else rejectChange(id);
  void nextTick(() => {
    for (const [el, top] of positions) {
      if (!el.isConnected) continue;
      const delta = top - el.getBoundingClientRect().top;
      if (!delta) continue;
      const animation = el.animate([{ transform: `translateY(${delta}px)` }, { transform: 'translateY(0)' }], { duration: 340, delay: 220, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'backwards' });
      const cleanup = () => { animation.cancel(); decisionAnimations.delete(cleanup); };
      decisionAnimations.add(cleanup);
      animation.finished.then(cleanup, cleanup);
    }
  });
}
onBeforeUnmount(() => { for (const cleanup of decisionAnimations) cleanup(); });

const meta = (cat) => REVIEW_CATEGORY_META[cat] || REVIEW_CATEGORY_META.fix;
const confidenceLabel = (level) => REVIEW_CONFIDENCE_LABEL[level] || '';

const headRubric = computed(() => {
  if (review.loading) return 'WIRD GEPRÜFT';
  if (review.error) return 'PRÜFUNG UNTERBROCHEN';
  return `VERBESSERUNGEN · ${review.changes.length}`;
});

const toolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: REVIEW_SORT_OPTIONS.find((o) => o.value === review.sort)?.label || 'Sortierung',
    value: review.sort,
    options: REVIEW_SORT_OPTIONS,
    minWidth: 180,
  },
  {
    key: 'filter',
    icon: 'mdi-filter-variant',
    label: { all: 'Alle', rejected: 'Abgelehnt', open: 'Offen' }[review.filter] || 'Offen',
    value: review.filter,
    active: review.filter !== 'open',
    options: [
      { value: 'all', label: 'Alle' },
      { value: 'open', label: openCount.value ? `Offen (${openCount.value})` : 'Offen' },
      { value: 'rejected', label: rejectedCount.value ? `Abgelehnt (${rejectedCount.value})` : 'Abgelehnt' },
    ],
    minWidth: 180,
  },
]);
function onToolbarAction({ action, value }) {
  if (action === 'sort') setSort(value);
  else if (action === 'filter') setFilter(value);
}
</script>

<style scoped src="./styles/review.css"></style>
