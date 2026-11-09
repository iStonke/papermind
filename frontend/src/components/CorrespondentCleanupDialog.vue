<template>
  <BaseDialog
    :model-value="modelValue"
    title="Aufräumen"
    icon="mdi-broom"
    primary-text="Fertig"
    :show-secondary="false"
    :persistent="busy"
    max-width="600"
    scrollable
    card-class="corr-cleanup-dialog"
    @update:model-value="close"
    @primary="close(false)"
  >
    <div class="corr-cleanup">
      <p v-if="!shortNames.length && !empties.length" class="corr-cleanup__empty" role="status">
        Alles aufgeräumt – keine Vorschläge.
      </p>

      <section v-if="shortNames.length" class="corr-cleanup__section" aria-labelledby="corr-cleanup-short">
        <h3 id="corr-cleanup-short">Kurznamen nachtragen <span class="corr-cleanup__count">{{ shortNames.length }}</span></h3>
        <p class="corr-cleanup__hint">Ohne Rechtsform – so erscheinen sie in Listen, Titeln und Dateinamen.</p>
        <ul class="corr-cleanup__list" aria-label="Kurznamen nachtragen">
          <li v-for="entry in shortNames" :key="entry.id" class="corr-cleanup__row">
            <v-checkbox-btn
              :model-value="pickedShortNames.has(entry.id)"
              :disabled="busy"
              density="compact"
              :aria-label="`Kurzname ${entry.suggestion} für ${entry.name}`"
              @update:model-value="toggle(pickedShortNames, entry.id, $event)"
            />
            <span class="corr-cleanup__text">
              <span class="corr-cleanup__name">{{ entry.name }} <span class="corr-cleanup__arrow" aria-hidden="true">→</span> <strong>{{ entry.suggestion }}</strong></span>
            </span>
          </li>
        </ul>
        <div class="corr-cleanup__actions">
          <v-btn class="text-none" variant="tonal" color="primary" size="small" :disabled="busy || !pickedShortNames.size" :loading="running === 'short'" @click="applyShortNames">
            {{ countLabel(pickedShortNames.size, 'Kurzname', 'Kurznamen') }} übernehmen
          </v-btn>
        </div>
      </section>

      <section v-if="empties.length" class="corr-cleanup__section" aria-labelledby="corr-cleanup-empty">
        <h3 id="corr-cleanup-empty">Ohne Dokumente <span class="corr-cleanup__count">{{ empties.length }}</span></h3>
        <p class="corr-cleanup__hint">Einträge ohne Dokumente und ohne zugeordnete Personen oder Mitglieder.</p>
        <ul class="corr-cleanup__list" aria-label="Ohne Dokumente">
          <li v-for="entry in empties" :key="entry.id" class="corr-cleanup__row">
            <v-checkbox-btn
              :model-value="pickedEmpties.has(entry.id)"
              :disabled="busy"
              density="compact"
              :aria-label="`${entry.name} löschen`"
              @update:model-value="toggle(pickedEmpties, entry.id, $event)"
            />
            <span class="corr-cleanup__text">
              <span class="corr-cleanup__name">{{ entry.name }}</span>
              <span class="corr-cleanup__meta">{{ kindLabel(entry.kind) }}<template v-if="entry.aliases?.length"> · {{ countLabel(entry.aliases.length, 'Alias', 'Aliase') }}</template></span>
            </span>
          </li>
        </ul>
        <div class="corr-cleanup__actions">
          <button v-if="pickedEmpties.size" type="button" class="corr-cleanup__action" :disabled="busy" @click="pickAllEmpties(false)">Auswahl aufheben</button>
          <button v-else type="button" class="corr-cleanup__action" :disabled="busy" @click="pickAllEmpties(true)">Alle auswählen</button>
          <template v-if="confirmDelete">
            <button type="button" class="corr-cleanup__action" :disabled="busy" @click="confirmDelete = false">Abbrechen</button>
            <v-btn class="text-none" variant="flat" color="error" size="small" :loading="running === 'delete'" :disabled="busy" @click="deleteEmpties">
              {{ countLabel(pickedEmpties.size, 'Eintrag', 'Einträge') }} endgültig löschen
            </v-btn>
          </template>
          <v-btn v-else class="text-none" variant="tonal" color="error" size="small" :disabled="busy || !pickedEmpties.size" @click="confirmDelete = true">
            {{ pickedEmpties.size ? `${countLabel(pickedEmpties.size, 'Eintrag', 'Einträge')} löschen …` : 'Löschen …' }}
          </v-btn>
        </div>
      </section>
      <p v-if="error" class="corr-cleanup__error" role="alert">{{ error }}</p>
    </div>
  </BaseDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BaseDialog from './BaseDialog.vue';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { mapApiError } from '../stores/notifications.js';
import { correspondentKindLabel } from '../utils/correspondentHierarchy.js';
import { findCleanupSuggestions } from '../utils/correspondentCleanup.js';

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(['update:modelValue']);
const store = useCorrespondentStore();

const pickedShortNames = ref(new Set());
const pickedEmpties = ref(new Set());
const confirmDelete = ref(false);
const running = ref('');
const error = ref('');
const busy = computed(() => Boolean(running.value));

const suggestions = computed(() => findCleanupSuggestions(store.correspondents, store.membersOf));
const shortNames = computed(() => suggestions.value.shortNames);
const empties = computed(() => suggestions.value.empties);

watch(() => props.modelValue, open => {
  if (!open) return;
  // Kurznamen sind vorausgewählt (harmlos, jederzeit änderbar); Löschen nie.
  pickedShortNames.value = new Set(shortNames.value.map(entry => entry.id));
  pickedEmpties.value = new Set();
  confirmDelete.value = false;
  error.value = '';
}, { immediate: true });

const countLabel = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const kindLabel = kind => correspondentKindLabel(kind);

function toggle(set, id, on) {
  const next = new Set(set.value);
  if (on) next.add(id);
  else next.delete(id);
  set.value = next;
  if (set === pickedEmpties) confirmDelete.value = false;
}

function pickAllEmpties(on) {
  pickedEmpties.value = on ? new Set(empties.value.map(entry => entry.id)) : new Set();
  confirmDelete.value = false;
}

async function applyShortNames() {
  const picked = shortNames.value.filter(entry => pickedShortNames.value.has(entry.id));
  running.value = 'short';
  error.value = '';
  let failed = 0;
  for (const entry of picked) {
    try {
      await store.updateCorrespondent(entry.id, { short_name: entry.suggestion }, { silent: true });
    } catch {
      failed += 1;
    }
  }
  running.value = '';
  pickedShortNames.value = new Set();
  if (failed) error.value = `${countLabel(failed, 'Kurzname konnte', 'Kurznamen konnten')} nicht gespeichert werden.`;
}

async function deleteEmpties() {
  const picked = empties.value.filter(entry => pickedEmpties.value.has(entry.id));
  running.value = 'delete';
  error.value = '';
  const failures = [];
  for (const entry of picked) {
    try {
      await store.deleteCorrespondent(entry.id);
    } catch (err) {
      failures.push(mapApiError(err, `„${entry.name}“ konnte nicht gelöscht werden.`));
    }
  }
  running.value = '';
  pickedEmpties.value = new Set();
  confirmDelete.value = false;
  if (failures.length) error.value = failures.length === 1 ? failures[0] : `${failures.length} Einträge konnten nicht gelöscht werden.`;
}

function close(open = false) {
  if (busy.value) return;
  emit('update:modelValue', open);
}
</script>

<style scoped>
.corr-cleanup { display: flex; flex-direction: column; gap: 22px; }
.corr-cleanup__empty { margin: 0; color: rgb(var(--v-theme-on-surface-variant)); }
.corr-cleanup__section { display: flex; flex-direction: column; gap: 8px; }
.corr-cleanup__section h3 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 0.95rem; font-weight: 600; }
.corr-cleanup__count {
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), .08);
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1.6;
}
.corr-cleanup__hint { margin: -4px 0 0; color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; }
.corr-cleanup__list {
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), .12);
  border-radius: 10px;
  list-style: none;
}
.corr-cleanup__row { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 4px 12px 4px 6px; }
.corr-cleanup__row :deep(.v-selection-control) { flex: none; }
.corr-cleanup__row + .corr-cleanup__row { border-top: 1px solid rgba(var(--v-theme-on-surface), .08); }
.corr-cleanup__text { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; padding-inline-start: 6px; line-height: 1.3; }
.corr-cleanup__name { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.corr-cleanup__arrow { color: rgb(var(--v-theme-on-surface-variant)); }
.corr-cleanup__meta { color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; }
.corr-cleanup__actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.corr-cleanup__action {
  flex: none;
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
.corr-cleanup__action:hover:not(:disabled) { text-decoration: underline; }
.corr-cleanup__action:disabled { opacity: .5; cursor: default; }
.corr-cleanup__action:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 1px; }
.corr-cleanup__actions :deep(.v-btn) { letter-spacing: normal; }
.corr-cleanup__error { margin: 0; color: rgb(var(--v-theme-error)); font-size: 13px; }
@media (pointer: coarse) { .corr-cleanup__action { min-height: 44px; } }
</style>
