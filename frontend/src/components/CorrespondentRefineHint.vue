<template>
  <!-- So spezifisch wie belegt: Sammlung → ihre Organisationen, Organisation → im Briefkopf genannte Person. -->
  <Transition name="refine-hint">
    <div v-if="visibleItems.length" class="refine-hint" role="group" :aria-label="label">
      <span class="refine-hint__label">{{ label }}</span>
      <button
        v-for="item in visibleItems"
        :key="item.id"
        type="button"
        class="refine-hint__chip"
        :class="{ 'is-mentioned': item.mentioned }"
        :disabled="disabled"
        :title="item.mentioned ? `${correspondentDisplayName(item)} – im Dokument genannt` : correspondentDisplayName(item)"
        :aria-label="`Genauer zuordnen: ${correspondentDisplayName(item)}${item.mentioned ? ' (im Dokument genannt)' : ''}`"
        @click="emit('apply', item.id)"
      >
        <v-icon size="14" aria-hidden="true">{{ item.mentioned ? 'mdi-text-search' : kindIcon(item.kind) }}</v-icon>
        {{ correspondentDisplayName(item) }}
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { correspondentDisplayName } from '../utils/correspondentHierarchy.js';
import { computed, ref, watch } from 'vue';
import { getCorrespondentRefinements } from '../api/correspondents.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { correspondentKindIcon } from '../utils/correspondentHierarchy.js';

const MAX_CHIPS = 6;
const props = defineProps({
  documentId: { type: String, default: null },
  correspondentId: { type: String, default: null },
  disabled: Boolean,
});
const emit = defineEmits(['apply']);
const store = useCorrespondentStore();
const items = ref([]);
let request = 0;

const correspondent = computed(() => store.findById(props.correspondentId));
const kind = computed(() => correspondent.value?.kind);
const members = computed(() => (correspondent.value ? store.membersOf(correspondent.value.id) : []));

// Sammlung: immer ihre Mitglieder anbieten (genannte zuerst); Organisation: nur genannte Personen.
const visibleItems = computed(() => {
  if (kind.value === 'collection') {
    const known = items.value.length
      ? items.value
      : members.value.map(member => ({ ...member, mentioned: false })).sort((a, b) => correspondentDisplayName(a).localeCompare(correspondentDisplayName(b), 'de-DE'));
    return known.slice(0, MAX_CHIPS);
  }
  if (kind.value === 'organization') return items.value.filter(item => item.mentioned).slice(0, MAX_CHIPS);
  return [];
});
const label = computed(() => (kind.value === 'collection' ? 'Sammlung – genauer:' : 'Genauer:'));

watch(() => [props.documentId, props.correspondentId, members.value.length], async ([documentId, correspondentId, memberCount]) => {
  const current = ++request;
  items.value = [];
  if (!documentId || !correspondentId || !memberCount || !['collection', 'organization'].includes(kind.value)) return;
  try {
    const result = await getCorrespondentRefinements(correspondentId, documentId);
    if (current === request) items.value = result?.items ?? [];
  } catch {
    // Nur ein Hinweis: ohne Antwort bleibt es bei der Mitgliederliste bzw. ohne Vorschlag.
  }
}, { immediate: true });

function kindIcon(value) {
  return correspondentKindIcon(value) || 'mdi-help-circle-outline';
}
</script>

<style scoped>
.refine-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 0.8rem;
}
.refine-hint__label { color: var(--pm-muted, rgb(var(--v-theme-on-surface-variant))); }
.refine-hint__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 220px;
  min-height: 26px;
  padding: 0 9px;
  overflow: hidden;
  border: 1px solid var(--pm-divider, rgba(var(--v-theme-on-surface), .16));
  border-radius: 999px;
  background: transparent;
  color: var(--pm-list-title, rgb(var(--v-theme-on-surface)));
  font: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color 140ms ease, border-color 140ms ease;
}
.refine-hint__chip:hover:not(:disabled) { background: color-mix(in srgb, var(--pm-accent, rgb(var(--v-theme-primary))) 8%, transparent); }
.refine-hint__chip.is-mentioned {
  border-color: color-mix(in srgb, var(--pm-accent, rgb(var(--v-theme-primary))) 55%, transparent);
  color: var(--pm-accent, rgb(var(--v-theme-primary)));
}
.refine-hint__chip:disabled { opacity: .5; cursor: default; }
.refine-hint__chip:focus-visible { outline: 2px solid var(--pm-accent, rgb(var(--v-theme-primary))); outline-offset: 2px; }
.refine-hint-enter-active, .refine-hint-leave-active { transition: opacity 160ms ease, transform 200ms cubic-bezier(.22, 1, .36, 1); }
.refine-hint-enter-from, .refine-hint-leave-to { opacity: 0; transform: translateY(-3px); }
:global(.pm-no-animations .refine-hint-enter-active),
:global(.pm-no-animations .refine-hint-leave-active),
:global(.pm-no-animations .refine-hint__chip) { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .refine-hint-enter-active, .refine-hint-leave-active, .refine-hint__chip { transition: none; }
}
@media (pointer: coarse) { .refine-hint__chip { min-height: 44px; } }
</style>
