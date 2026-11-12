<template>
  <section class="dupes" aria-labelledby="dupes-title">
    <slot name="back" />
    <header class="dupes__head">
      <span class="dupes__icon" aria-hidden="true"><v-icon size="22">mdi-source-merge</v-icon></span>
      <div class="dupes__heading">
        <h1 id="dupes-title" ref="titleRef" tabindex="-1" class="dupes__title">Mögliche Doppelte</h1>
        <p class="dupes__subtitle">{{ subtitle }}</p>
      </div>
      <!-- Kopfaktionen wie im Profilkopf: umrandete Icon-Buttons, Zahl als Plakette. -->
      <div class="dupes__head-actions">
        <span v-if="!showHidden" class="dupes__action">
          <v-btn
            class="pm-header-icon-btn dupes__head-btn"
            variant="outlined"
            icon="mdi-broom"
            aria-label="Aufräumen …"
            aria-haspopup="dialog"
            title="Aufräumen: Doppelte, Kurznamen und leere Einträge"
            @click="emit('cleanup')"
          />
          <span v-if="cleanupCount" class="dupes__badge dupes__badge--accent" aria-hidden="true">{{ cleanupCount }}</span>
        </span>
        <!-- Immer sichtbar; ohne ausgeblendete Paare ausgegraut. -->
        <span class="dupes__action" :title="hiddenTitle">
          <v-btn
            class="pm-header-icon-btn dupes__head-btn"
            :class="{ 'is-active': showHidden }"
            variant="outlined"
            :icon="showHidden ? 'mdi-arrow-left' : 'mdi-eye-off-outline'"
            :disabled="!showHidden && !hiddenPairs.length"
            :aria-pressed="showHidden"
            :aria-label="showHidden ? 'Offene anzeigen' : `Ausgeblendete Paare (${hiddenPairs.length})`"
            @click="toggleHidden"
          />
          <span v-if="!showHidden && hiddenPairs.length" class="dupes__badge" aria-hidden="true">{{ hiddenPairs.length }}</span>
        </span>
      </div>
    </header>

    <div class="dupes__scroll">
      <template v-if="showHidden">
        <TransitionGroup v-if="hiddenPairs.length" tag="ul" name="dupes-card" class="dupes__list" aria-label="Ausgeblendete Paare">
          <li v-for="pair in hiddenPairs" :key="pair.key" class="dupes__card dupes__card--hidden">
            <div class="dupes__pair">
              <button
                v-for="(entry, index) in [pair.a, pair.b]"
                :key="entry.id"
                type="button"
                class="dupes__entry"
                :class="{ 'dupes__entry--second': index === 1 }"
                :aria-label="`${correspondentDisplayName(entry)} öffnen`"
                @click="emit('open', entry.id)"
              >
                <v-icon class="dupes__entry-icon" size="18" aria-hidden="true">{{ kindIcon(entry.kind) }}</v-icon>
                <span class="dupes__entry-text">
                  <span class="dupes__entry-name" :title="entry.name">{{ correspondentDisplayName(entry) }}</span>
                  <span class="dupes__entry-meta">{{ meta(entry) }}</span>
                </span>
              </button>
              <v-icon class="dupes__link" size="18" aria-hidden="true">mdi-swap-horizontal</v-icon>
            </div>
            <div class="dupes__foot">
              <span class="dupes__reason">Als „Kein Doppel“ markiert</span>
              <span class="dupes__actions">
                <v-btn
                  class="text-none"
                  variant="text"
                  size="small"
                  prepend-icon="mdi-undo"
                  :disabled="busyKey === pair.key"
                  :aria-label="`${correspondentDisplayName(pair.a)} und ${correspondentDisplayName(pair.b)} wieder anzeigen`"
                  @click="emit('restore', pair.key)"
                >Wieder anzeigen</v-btn>
              </span>
            </div>
          </li>
        </TransitionGroup>
        <PmEmptyState v-else icon="mdi-eye-off-outline" title="Keine ausgeblendeten Paare." size="md" role="status" />
      </template>
      <PmEmptyState
        v-else-if="!pairs.length"
        icon="mdi-check-circle-outline"
        title="Keine möglichen Doppelten."
        subtitle="Neue Vorschläge erscheinen hier automatisch."
        size="md"
        role="status"
      />
      <TransitionGroup v-else tag="ul" name="dupes-card" class="dupes__list" aria-label="Paare">
        <li v-for="pair in pairs" :key="pair.key" class="dupes__card">
          <div class="dupes__pair">
            <button
              v-for="(entry, index) in [pair.a, pair.b]"
              :key="entry.id"
              type="button"
              class="dupes__entry"
              :class="{ 'dupes__entry--second': index === 1 }"
              :aria-label="`${correspondentDisplayName(entry)} öffnen`"
              @click="emit('open', entry.id)"
            >
              <v-icon class="dupes__entry-icon" size="18" aria-hidden="true">{{ kindIcon(entry.kind) }}</v-icon>
              <span class="dupes__entry-text">
                <span class="dupes__entry-name" :title="entry.name">{{ correspondentDisplayName(entry) }}</span>
                <span class="dupes__entry-meta">{{ meta(entry) }}</span>
              </span>
            </button>
            <v-icon class="dupes__link" size="18" aria-hidden="true">mdi-swap-horizontal</v-icon>
          </div>
          <div class="dupes__foot">
            <span class="dupes__reason">{{ pair.label }}</span>
            <span class="dupes__actions">
              <button
                type="button"
                class="dupes__dismiss"
                :disabled="busyKey === pair.key"
                :aria-label="`${correspondentDisplayName(pair.a)} und ${correspondentDisplayName(pair.b)}: kein Doppel`"
                @click="emit('dismiss', pair.key)"
              >Kein Doppel</button>
              <v-btn
                class="text-none"
                variant="tonal"
                color="primary"
                size="small"
                prepend-icon="mdi-source-merge"
                :aria-label="`${correspondentDisplayName(pair.a)} und ${correspondentDisplayName(pair.b)} zusammenführen`"
                @click="emit('merge', { subjectId: pair.a.id, otherId: pair.b.id })"
              >Zusammenführen …</v-btn>
            </span>
          </div>
        </li>
      </TransitionGroup>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue';
import PmEmptyState from './PmEmptyState.vue';
import { correspondentDisplayName, correspondentKindIcon, correspondentKindLabel } from '../utils/correspondentHierarchy.js';

const props = defineProps({
  pairs: { type: Array, required: true },
  busyKey: { type: String, default: '' },
  /** Als „Kein Doppel“ markierte Paare, die es noch gibt. */
  hiddenPairs: { type: Array, default: () => [] },
  /** Anzahl der Aufräum-Vorschläge (Plakette am Besen). */
  cleanupCount: { type: Number, default: 0 },
});
const emit = defineEmits(['merge', 'dismiss', 'open', 'restore', 'cleanup']);
const titleRef = ref(null);
const showHidden = ref(false);

async function toggleHidden() {
  showHidden.value = !showHidden.value;
  await nextTick();
  titleRef.value?.focus();
}

const hiddenTitle = computed(() => {
  if (showHidden.value) return 'Offene anzeigen';
  return props.hiddenPairs.length ? `Ausgeblendete Paare (${props.hiddenPairs.length})` : 'Ausgeblendete Paare: Keine als „Kein Doppel“ markiert';
});

const subtitle = computed(() => {
  if (showHidden.value) {
    const hidden = props.hiddenPairs.length;
    return `${hidden === 1 ? '1 Paar' : `${hidden} Paare`} · als „Kein Doppel“ markiert`;
  }
  const count = props.pairs.length;
  if (!count) return 'Alles geprüft';
  return `${count === 1 ? '1 Paar' : `${count} Paare`} · prüfen und zusammenführen`;
});

function kindIcon(kind) {
  return correspondentKindIcon(kind) || 'mdi-help-circle-outline';
}

function meta(entry) {
  const count = Number(entry.usage_count || 0);
  const parts = [correspondentKindLabel(entry.kind), count === 1 ? '1 Dokument' : `${count} Dokumente`];
  const aliases = (entry.aliases || []).length;
  if (aliases) parts.push(aliases === 1 ? '1 Alias' : `${aliases} Aliase`);
  return parts.join(' · ');
}

defineExpose({ focusTitle: () => titleRef.value?.focus() });
</script>

<style scoped>
.dupes { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; }
.dupes__head {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  box-sizing: border-box;
  min-height: calc(57px + var(--notes-meta-row-height, 36px));
  padding: 10px clamp(18px, 3vw, 40px);
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-app-surface);
}
.dupes__icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--pm-warning) 12%, transparent);
  color: var(--pm-warning);
}
.dupes__heading { flex: 1; min-width: 0; }
.dupes__head-actions { display: flex; flex: none; align-items: center; gap: 10px; }
.dupes__action { position: relative; display: inline-flex; }
.dupes__head-btn.v-btn { border-color: var(--pm-divider); color: var(--pm-muted); }
.dupes__head-btn.v-btn.is-active { border-color: var(--pm-accent); color: var(--pm-accent-text); }
.dupes__badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border: 2px solid var(--pm-app-surface);
  border-radius: 999px;
  background: var(--pm-muted);
  color: var(--pm-app-surface);
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 14px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.dupes__badge--accent { background: var(--pm-accent); color: var(--pm-accent-contrast, #fff); }
.dupes__card--hidden .dupes__entry { opacity: 0.8; }
.dupes__title { margin: 0; font-size: 1.5rem; font-weight: 700; line-height: 1.2; outline: none; }
.dupes__subtitle { margin: 4px 0 0; color: var(--pm-muted); font-size: 0.86rem; }
.dupes__scroll { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 22px clamp(16px, 3vw, 40px) 40px; }
.dupes__list { display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; list-style: none; }
.dupes__card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  background: var(--pm-app-surface);
}
.dupes__pair { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.dupes__entry {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 48px;
  padding: 6px 10px;
  border: 0;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-list-title, currentColor) 4%, transparent);
  color: var(--pm-list-title);
  font: inherit;
  text-align: start;
  cursor: pointer;
  transition: background-color 140ms ease;
}
.dupes__entry:hover { background: color-mix(in srgb, var(--pm-list-title, currentColor) 8%, transparent); }
.dupes__entry:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.dupes__entry-icon { flex: none; color: var(--pm-muted); }
.dupes__entry-text { display: flex; flex-direction: column; min-width: 0; line-height: 1.3; }
.dupes__entry-name { overflow: hidden; font-size: 0.95rem; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.dupes__entry-meta { overflow: hidden; color: var(--pm-muted); font-size: 0.78rem; text-overflow: ellipsis; white-space: nowrap; }
.dupes__link { position: absolute; top: 50%; left: 50%; color: var(--pm-muted); transform: translate(-50%, -50%); }
.dupes__foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 12px; }
.dupes__actions :deep(.v-btn) { letter-spacing: normal; }
.dupes__reason { color: var(--pm-muted); font-size: 0.82rem; }
.dupes__actions { display: inline-flex; align-items: center; gap: 12px; margin-inline-start: auto; }
.dupes__dismiss {
  min-height: 28px;
  padding: 0 4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.86rem;
  cursor: pointer;
}
.dupes__dismiss:hover:not(:disabled) { color: var(--pm-list-title); text-decoration: underline; }
.dupes__dismiss:disabled { opacity: .5; cursor: default; }
.dupes__dismiss:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.dupes-card-leave-active { transition: opacity 180ms ease, transform 220ms cubic-bezier(.22, 1, .36, 1); }
.dupes-card-leave-to { opacity: 0; transform: translateX(12px); }
.dupes-card-move { transition: transform 240ms cubic-bezier(.22, 1, .36, 1); }
:global(.pm-no-animations .dupes-card-leave-active),
:global(.pm-no-animations .dupes-card-move),
:global(.pm-no-animations .dupes__entry) { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .dupes-card-leave-active, .dupes-card-move, .dupes__entry { transition: none; }
}
@media (max-width: 640px) {
  .dupes__pair { grid-template-columns: 1fr; gap: 6px; }
  .dupes__entry { order: 1; }
  .dupes__link { position: static; order: 2; justify-self: center; transform: rotate(90deg); }
  .dupes__entry--second { order: 3; }
}
@media (pointer: coarse) { .dupes__dismiss { min-height: 44px; } }
</style>
