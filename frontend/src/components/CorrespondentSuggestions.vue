<template>
  <!-- Existing correspondents that match the typed name; shown inline below the
       name field and only while there are matches. -->
  <Transition name="corr-suggestions">
    <section v-if="visibleMatches.length" class="corr-suggestions" :class="{ 'is-exact': exact }" aria-label="Vorhandene Korrespondenten">
      <div class="corr-suggestions__inner">
        <p class="corr-suggestions__status" role="status">
          <v-icon size="16" aria-hidden="true">mdi-alert-circle-outline</v-icon>
          {{ status }}
        </p>
        <TransitionGroup tag="ul" name="corr-suggestion-row" class="corr-suggestions__list" aria-label="Passende Korrespondenten">
          <li v-for="(match, index) in visibleMatches" :key="match.correspondent.id" class="corr-suggestions__item" :style="{ '--row-index': index }">
            <v-icon class="corr-suggestions__icon" size="18" aria-hidden="true">{{ kindIcon(match.correspondent.kind) }}</v-icon>
            <span class="corr-suggestions__text">
              <span class="corr-suggestions__name">{{ match.correspondent.name }}</span>
              <span class="corr-suggestions__meta">{{ metaLine(match) }}</span>
            </span>
            <span class="corr-suggestions__actions">
              <button type="button" class="corr-suggestions__action" :disabled="busy || updating"
                :aria-label="`${match.correspondent.name} verwenden`" @click="emit('use', match.correspondent.id)">Verwenden</button>
              <template v-if="!exact">
                <span class="corr-suggestions__sep" aria-hidden="true">·</span>
                <button type="button" class="corr-suggestions__action" :disabled="busy || updating"
                  :aria-label="`Als Alias zu ${match.correspondent.name} hinzufügen`" @click="emit('alias', match.correspondent.id)">Als Alias</button>
              </template>
            </span>
          </li>
        </TransitionGroup>
      </div>
    </section>
  </Transition>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { correspondentKindIcon, correspondentKindLabel } from '../utils/correspondentHierarchy.js';

const props = defineProps({ matches: { type: Array, default: () => [] }, exact: Boolean, busy: Boolean, name: { type: String, default: '' } });
const emit = defineEmits(['use', 'alias']);
const visibleMatches = ref([]);
const updating = ref(false);
let timer;
// Debounced so the list does not flicker while typing.
watch(() => [props.matches, props.name], () => {
  clearTimeout(timer);
  updating.value = true;
  timer = setTimeout(() => {
    visibleMatches.value = props.matches;
    updating.value = false;
  }, 250);
}, { immediate: true });
onBeforeUnmount(() => clearTimeout(timer));

const status = computed(() => {
  if (props.exact) return 'Dieser Name ist bereits vorhanden.';
  const [first] = visibleMatches.value;
  if (first?.legalFormOnly) return `„${first.matchedName}“ ist bereits vorhanden – nur die Rechtsform unterscheidet sich.`;
  const count = visibleMatches.value.length;
  return count === 1 ? '1 ähnlicher Eintrag vorhanden' : `${count} ähnliche Einträge vorhanden`;
});

function kindIcon(kind) {
  return correspondentKindIcon(kind) || 'mdi-help-circle-outline';
}

function metaLine({ correspondent, matchedName }) {
  const count = Number(correspondent.total_count ?? correspondent.usage_count ?? 0);
  const parts = [correspondentKindLabel(correspondent.kind)];
  if (correspondent.parent_name) parts.push(correspondent.parent_name);
  parts.push(count === 1 ? '1 Dokument' : `${count} Dokumente`);
  if (matchedName !== correspondent.name) parts.push(`Alias: ${matchedName}`);
  return parts.join(' · ');
}
</script>
<style scoped>
.corr-suggestions {
  /* Grid rows let the box unfold to its natural height. */
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, rgb(var(--v-theme-warning)) 45%, transparent);
  border-radius: 10px;
}
.corr-suggestions__inner { min-height: 0; overflow: hidden; }

/* Unfold: height opens, box fades in; the parent's gap (12px) is taken back
   while collapsed so nothing jumps. Content follows slightly later. */
.corr-suggestions-enter-active,
.corr-suggestions-leave-active {
  transition:
    grid-template-rows 320ms cubic-bezier(.22, 1, .36, 1),
    margin-block-start 320ms cubic-bezier(.22, 1, .36, 1),
    border-color 240ms ease,
    opacity 200ms ease;
}
.corr-suggestions-leave-active { transition-duration: 220ms, 220ms, 160ms, 160ms; }
.corr-suggestions-enter-from,
.corr-suggestions-leave-to {
  grid-template-rows: 0fr;
  margin-block-start: calc(-1 * var(--corr-suggestions-gap, 12px));
  border-color: transparent;
  opacity: 0;
}
.corr-suggestions-enter-active .corr-suggestions__inner { transition: transform 360ms cubic-bezier(.22, 1, .36, 1); }
.corr-suggestions-enter-from .corr-suggestions__inner { transform: translateY(-6px); }

/* Rows cascade in while typing narrows or widens the matches. */
.corr-suggestion-row-enter-active {
  transition: opacity 220ms ease, transform 260ms cubic-bezier(.22, 1, .36, 1);
  transition-delay: calc(min(var(--row-index, 0), 5) * 40ms + 60ms);
}
.corr-suggestion-row-enter-from { opacity: 0; transform: translateY(-4px); }
.corr-suggestion-row-leave-active { transition: opacity 120ms ease; }
.corr-suggestion-row-leave-to { opacity: 0; }
.corr-suggestion-row-move { transition: transform 240ms cubic-bezier(.22, 1, .36, 1); }

:global(.pm-no-animations .corr-suggestions-enter-active),
:global(.pm-no-animations .corr-suggestions-leave-active),
:global(.pm-no-animations .corr-suggestions-enter-active .corr-suggestions__inner),
:global(.pm-no-animations .corr-suggestion-row-enter-active),
:global(.pm-no-animations .corr-suggestion-row-leave-active),
:global(.pm-no-animations .corr-suggestion-row-move) { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .corr-suggestions-enter-active, .corr-suggestions-leave-active,
  .corr-suggestions-enter-active .corr-suggestions__inner,
  .corr-suggestion-row-enter-active, .corr-suggestion-row-leave-active,
  .corr-suggestion-row-move { transition: none; }
}
.corr-suggestions__status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 7px 12px;
  background: color-mix(in srgb, rgb(var(--v-theme-warning)) 12%, transparent);
  color: rgb(var(--v-theme-on-surface));
  font-size: 12px;
}
.corr-suggestions__status .v-icon { color: rgb(var(--v-theme-warning)); }
.corr-suggestions__list { max-height: 196px; margin: 0; padding: 0; overflow-y: auto; list-style: none; }
.corr-suggestions__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), .08);
}
.corr-suggestions__item:first-child { border-top: 0; }
.corr-suggestions__icon { flex: none; color: rgb(var(--v-theme-on-surface-variant)); }
.corr-suggestions__text { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; line-height: 1.3; }
.corr-suggestions__name { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.corr-suggestions__meta { overflow: hidden; color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.corr-suggestions__actions { display: inline-flex; flex: none; align-items: center; gap: 4px; }
.corr-suggestions__sep { color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; }
.corr-suggestions__action {
  min-height: 28px;
  padding: 0 4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: rgb(var(--v-theme-primary));
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.corr-suggestions__action:hover:not(:disabled) { text-decoration: underline; }
.corr-suggestions__action:disabled { opacity: .5; cursor: default; }
.corr-suggestions__action:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 1px; }
@media (max-width: 480px) {
  .corr-suggestions__item { flex-wrap: wrap; }
  .corr-suggestions__actions { flex-basis: 100%; padding-left: 28px; }
}
@media (pointer: coarse) {
  .corr-suggestions__action { min-height: 44px; }
}
</style>
