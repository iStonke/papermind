<template>
  <div class="retention-form" @click.stop>
    <div class="retention-form__grid">
      <div class="retention-form__field">
        <label>Aufbewahrungsdauer</label>
        <v-select
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
      <div class="retention-form__field">
        <label>Ablaufdatum</label>
        <div class="retention-form__static">{{ expiryLabel || '—' }}</div>
      </div>
    </div>

    <div class="retention-toggle-row">
      <div class="retention-toggle-row__text">
        <div class="retention-toggle-row__title">Original behalten</div>
        <div class="retention-toggle-row__hint">Physisches Original muss aufbewahrt werden</div>
      </div>
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
    </div>

    <div class="retention-form__field">
      <label>Begründung</label>
      <v-textarea
        :model-value="reason"
        :rows="2"
        :max-rows="4"
        auto-grow
        density="compact"
        variant="outlined"
        hide-details
        class="retention-form__input"
        placeholder="Kurzer Grund, z. B. Rechtsgrundlage…"
        @update:model-value="$emit('update:reason', $event)"
      />
    </div>

    <div v-if="errorMessage" class="retention-form__error">{{ errorMessage }}</div>
    <div class="retention-form__disclaimer">KI-Hinweis, keine Rechtsberatung. Vor Vernichtung prüfen.</div>

    <div v-if="showActions" class="retention-form__actions">
      <v-btn
        v-if="allowSuggest && state !== 'ai'"
        size="small"
        variant="text"
        class="retention-form__ai"
        :loading="suggesting"
        :disabled="suggesting"
        @click="$emit('suggest')"
      >
        <v-icon size="14" start>mdi-auto-fix</v-icon>
        KI-Bewertung
      </v-btn>
      <v-btn
        size="small"
        variant="text"
        class="retention-form__cancel"
        :disabled="saving"
        @click="$emit('cancel')"
      >
        Abbrechen
      </v-btn>
      <v-btn
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
import { computed } from 'vue';

const props = defineProps({
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
  'save',
  'suggest',
  'cancel'
]);

// Toggle „Original behalten": keep ↔ scan_sufficient auf paper_original.
const keepOriginal = computed({
  get: () => props.paperOriginal === 'keep',
  set: (value) => emit('update:paperOriginal', value ? 'keep' : 'scan_sufficient')
});
</script>
