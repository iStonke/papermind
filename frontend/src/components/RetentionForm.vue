<template>
  <div class="retention-form" @click.stop>
    <div class="retention-form__grid">
      <div class="retention-form__field">
        <label :for="`${fieldId}-period`">{{ compact ? 'Dauer' : 'Aufbewahrungsdauer' }}</label>
        <div>
          <v-select
            :id="`${fieldId}-period`"
            :aria-label="compact ? 'Aufbewahrungsdauer' : undefined"
            :model-value="periodYears"
            :items="periodItems"
            density="compact"
            variant="outlined"
            hide-details
            class="retention-form__input"
            :menu-props="menuProps"
            @update:model-value="$emit('update:periodYears', $event)"
          />
        </div>
      </div>
      <div v-if="!compact" class="retention-form__field">
        <label :for="`${fieldId}-expiry`">Ablaufdatum</label>
        <output :id="`${fieldId}-expiry`" class="retention-form__static">{{ expiryLabel || '—' }}</output>
      </div>
    </div>

    <div class="retention-toggle-row">
      <div v-if="!compact" class="retention-toggle-row__text">
        <div class="retention-toggle-row__title">Original behalten</div>
        <div class="retention-toggle-row__hint">Physisches Original muss aufbewahrt werden</div>
      </div>
      <div class="retention-toggle-row__control">
        <button
          type="button"
          class="retention-toggle"
          :class="{ 'retention-toggle--on': keepOriginal }"
          role="switch"
          :aria-checked="String(keepOriginal)"
          aria-label="Original behalten"
          @click="keepOriginal = !keepOriginal"
        >
          <span class="retention-toggle__knob" />
        </button>
        <span v-if="compact" class="retention-toggle-row__value">Original behalten</span>
      </div>
    </div>

    <div class="retention-form__reason">
      <div class="retention-form__field">
        <label :for="`${fieldId}-reason`">Begründung</label>
        <v-textarea
          :id="`${fieldId}-reason`"
          :aria-label="compact ? 'Begründung' : undefined"
          :model-value="reason"
          :rows="compact ? 1 : 2"
          :max-rows="compact ? undefined : 4"
          auto-grow
          density="compact"
          variant="outlined"
          hide-details
          class="retention-form__input"
          placeholder="Kurzer Grund, z. B. Rechtsgrundlage…"
          @update:model-value="$emit('update:reason', $event)"
        />
      </div>
    </div>

    <div v-if="errorMessage" class="retention-form__error" role="alert">{{ errorMessage }}</div>

    <div v-if="showActions && (!compact || state === 'ai' || allowSuggest || dirty || saving)" class="retention-form__actions">
      <v-btn
        v-if="allowSuggest && state !== 'ai'"
        size="small"
        variant="text"
        class="retention-form__ai"
        :aria-busy="suggesting"
        :disabled="suggesting || saving"
        @click="$emit('suggest')"
      >
        <template #prepend>
          <v-progress-circular v-if="suggesting" indeterminate size="14" width="2" aria-hidden="true" />
          <v-icon v-else size="14" aria-hidden="true">mdi-auto-fix</v-icon>
        </template>
        {{ compact ? 'Mit KI prüfen' : 'KI-Bewertung' }}
      </v-btn>
      <v-btn
        v-if="!compact || dirty || (saving && !showAccept)"
        size="small"
        variant="text"
        class="retention-form__cancel"
        :disabled="saving"
        @click="$emit('cancel')"
      >
        {{ compact ? 'Verwerfen' : 'Abbrechen' }}
      </v-btn>
      <v-btn
        v-if="showAccept"
        size="small"
        color="primary"
        variant="flat"
        class="retention-form__save retention-form__accept"
        :loading="saving"
        :disabled="saving"
        @click="$emit('accept')"
      >
        Übernehmen
      </v-btn>
      <v-btn
        v-else-if="!compact || dirty || saving"
        size="small"
        color="primary"
        variant="flat"
        class="retention-form__save"
        :loading="saving"
        :disabled="saving"
        @click="$emit('save')"
      >
        Speichern
      </v-btn>
    </div>
  </div>
</template>

<script setup>
import { computed, useId } from 'vue';

const fieldId = `retention-${useId()}`;

const props = defineProps({
  compact: { type: Boolean, default: false },
  dirty: { type: Boolean, default: false },
  periodYears: { type: Number, default: null },
  paperOriginal: { type: String, default: 'unclear' },
  reason: { type: String, default: '' },
  expiryLabel: { type: String, default: '' },
  // Anzeigezustand der Leiste (empty/ai/filled); blendet KI-Button im ai-Zustand aus.
  state: { type: String, default: 'empty' },
  saving: { type: Boolean, default: false },
  suggesting: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  allowSuggest: { type: Boolean, default: true },
  menuProps: { type: Object, default: () => ({}) },
  periodItems: {
    type: Array,
    default: () => ([
      { title: 'Unklar', value: null },
      { title: 'Keine Aufbewahrungspflicht', value: 0 },
      { title: '3 Jahre', value: 3 },
      { title: '6 Jahre', value: 6 },
      { title: '10 Jahre', value: 10 },
      { title: '30 Jahre', value: 30 },
      { title: 'Unbegrenzt', value: -1 }
    ])
  },
  // Aktionsleiste (KI-Bewertung/Abbrechen/Speichern) ausblenden, wenn die Felder live binden.
  showActions: { type: Boolean, default: true }
});

const emit = defineEmits([
  'update:periodYears',
  'update:paperOriginal',
  'update:reason',
  'accept',
  'save',
  'suggest',
  'cancel'
]);

const showAccept = computed(() => props.compact && props.state === 'ai' && !props.dirty);

// Toggle „Original behalten": keep ↔ scan_sufficient auf paper_original.
const keepOriginal = computed({
  get: () => props.paperOriginal === 'keep',
  set: (value) => emit('update:paperOriginal', value ? 'keep' : 'scan_sufficient')
});
</script>
