<template>
  <BaseDialog
    v-model="dialogOpen"
    max-width="820"
    width="min(820px, calc(100vw - 96px))"
    scrollable
    :title="dialogTitle"
    :header-subtitle="dialogHeaderSubtitle"
    :description="dialogDescription"
    primary-text="Speichern"
    secondary-text="Abbrechen"
    :loading="loading"
    :primary-disabled="isSaveDisabled"
    @primary="submit"
    @close="handleClose"
  >
    <div class="sf-editor">
      <div class="sf-top-row">
        <v-text-field
          v-model="name"
          class="sf-top-row__name"
          label="Name"
          density="comfortable"
          variant="outlined"
          hide-details
        />

        <v-select
          v-model="matchOp"
          class="sf-top-row__match"
          label="Trefferlogik"
          density="comfortable"
          variant="outlined"
          hide-details
          :items="matchOptions"
          item-title="label"
          item-value="value"
        />
      </div>

      <section class="sf-rules">
        <div class="sf-rules__header">
          <span>Regeln</span>
        </div>

        <div class="sf-rules__list">
          <div v-for="rule in rules" :key="rule.id" class="sf-rule-row">
            <v-select
              :model-value="rule.field"
              density="comfortable"
              variant="outlined"
              hide-details
              :items="fieldOptions"
              item-title="label"
              item-value="value"
              @update:model-value="setRuleField(rule.id, $event)"
            />

            <v-select
              :model-value="rule.op"
              density="comfortable"
              variant="outlined"
              hide-details
              :items="operatorOptions(rule.field)"
              item-title="label"
              item-value="value"
              @update:model-value="setRuleOp(rule.id, $event)"
            />

            <div class="sf-rule-row__value">
              <template v-if="isNoValueOp(rule.op)">
                <div class="sf-rule-row__empty">Kein Wert nötig</div>
              </template>

              <template v-else-if="rule.op === 'between'">
                <div class="sf-range">
                  <v-text-field
                    :model-value="rule.from"
                    type="date"
                    density="comfortable"
                    variant="outlined"
                    hide-details
                    label="Von"
                    @update:model-value="setRuleRange(rule.id, 'from', $event)"
                  />
                  <v-text-field
                    :model-value="rule.to"
                    type="date"
                    density="comfortable"
                    variant="outlined"
                    hide-details
                    label="Bis"
                    @update:model-value="setRuleRange(rule.id, 'to', $event)"
                  />
                </div>
              </template>

              <template v-else-if="isListOp(rule.op)">
                <v-combobox
                  :model-value="rule.values"
                  :items="listValueOptions(rule.field)"
                  multiple
                  chips
                  closable-chips
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Werte"
                  @update:model-value="setRuleValues(rule.id, $event)"
                />
              </template>

              <template v-else-if="rule.field === 'ocr_status'">
                <v-select
                  :model-value="rule.value"
                  :items="ocrStatusOptions"
                  item-title="label"
                  item-value="value"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Status"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>

              <template v-else-if="rule.field === 'is_favorite'">
                <v-select
                  :model-value="rule.value"
                  :items="favoriteOptions"
                  item-title="label"
                  item-value="value"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Favorit"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>

              <template v-else-if="rule.field === 'tags'">
                <v-combobox
                  :model-value="rule.value"
                  :items="tagOptions"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Tag"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>

              <template v-else-if="rule.field === 'category'">
                <v-combobox
                  :model-value="rule.value"
                  :items="categoryOptions"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Kategorie"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>

              <template v-else-if="isDateField(rule.field)">
                <v-text-field
                  :model-value="rule.value"
                  type="date"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Datum"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>

              <template v-else>
                <v-text-field
                  :model-value="rule.value"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  label="Wert"
                  @update:model-value="setRuleValue(rule.id, $event)"
                />
              </template>
            </div>

            <v-btn
              icon="mdi-close"
              size="small"
              variant="text"
              :disabled="rules.length <= 1"
              aria-label="Regel entfernen"
              @click="removeRule(rule.id)"
            />
          </div>
        </div>

        <div class="sf-rules__footer">
          <v-btn class="sf-add-btn" variant="tonal" color="primary" prepend-icon="mdi-plus" @click="addRule">
            Regel hinzufügen
          </v-btn>
          <span class="sf-count sf-count--rules">
            <v-progress-circular v-if="preview.loading" indeterminate size="12" width="2" class="sf-count__spinner" />
            Treffer: {{ previewDisplayTotal }}
          </span>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="sf-footer">
        <div class="sf-footer__actions">
          <v-btn variant="text" :disabled="loading" @click="cancel">Abbrechen</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            :loading="loading"
            :disabled="isSaveDisabled || loading"
            @click="submit"
          >
            Speichern
          </v-btn>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import BaseDialog from './BaseDialog.vue';

const FIELD_OPTIONS = [
  { value: 'title', label: 'Titel' },
  { value: 'filename', label: 'Dateiname' },
  { value: 'tags', label: 'Tags' },
  { value: 'category', label: 'Kategorie' },
  { value: 'is_favorite', label: 'Favorit' },
  { value: 'ocr_text', label: 'OCR-Text' },
  { value: 'note', label: 'Notiz' },
  { value: 'doc_date', label: 'Dokumentdatum' },
  { value: 'created_at', label: 'Erstellt am' },
  { value: 'updated_at', label: 'Aktualisiert am' },
  { value: 'ocr_status', label: 'OCR-Status' }
];

const OPERATOR_MAP = {
  title: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'starts_with', label: 'beginnt mit' },
    { value: 'ends_with', label: 'endet mit' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'in', label: 'ist einer von' },
    { value: 'not_in', label: 'ist keiner von' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  filename: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'starts_with', label: 'beginnt mit' },
    { value: 'ends_with', label: 'endet mit' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'in', label: 'ist einer von' },
    { value: 'not_in', label: 'ist keiner von' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  tags: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'in', label: 'ist einer von' },
    { value: 'not_in', label: 'ist keiner von' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  category: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'starts_with', label: 'beginnt mit' },
    { value: 'ends_with', label: 'endet mit' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'in', label: 'ist einer von' },
    { value: 'not_in', label: 'ist keiner von' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  is_favorite: [
    { value: 'equals', label: 'ist' }
  ],
  ocr_text: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'starts_with', label: 'beginnt mit' },
    { value: 'ends_with', label: 'endet mit' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  note: [
    { value: 'contains', label: 'enthält' },
    { value: 'equals', label: 'ist' },
    { value: 'starts_with', label: 'beginnt mit' },
    { value: 'ends_with', label: 'endet mit' },
    { value: 'not_contains', label: 'enthält nicht' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  doc_date: [
    { value: 'equals', label: 'ist' },
    { value: 'before', label: 'vor' },
    { value: 'after', label: 'nach' },
    { value: 'between', label: 'zwischen' },
    { value: 'gte', label: 'ab (inkl.)' },
    { value: 'lte', label: 'bis (inkl.)' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  created_at: [
    { value: 'before', label: 'vor' },
    { value: 'after', label: 'nach' },
    { value: 'between', label: 'zwischen' },
    { value: 'gte', label: 'ab (inkl.)' },
    { value: 'lte', label: 'bis (inkl.)' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  updated_at: [
    { value: 'before', label: 'vor' },
    { value: 'after', label: 'nach' },
    { value: 'between', label: 'zwischen' },
    { value: 'gte', label: 'ab (inkl.)' },
    { value: 'lte', label: 'bis (inkl.)' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ],
  ocr_status: [
    { value: 'equals', label: 'ist' },
    { value: 'in', label: 'ist einer von' },
    { value: 'not_in', label: 'ist keiner von' },
    { value: 'is_empty', label: 'ist leer' },
    { value: 'is_not_empty', label: 'ist nicht leer' }
  ]
};

const OCR_STATUS_OPTIONS = [
  { value: 'not_started', label: 'Nicht gestartet' },
  { value: 'queued', label: 'Warteschlange' },
  { value: 'running', label: 'Läuft' },
  { value: 'done', label: 'Fertig' },
  { value: 'failed', label: 'Fehler' }
];

const FAVORITE_OPTIONS = [
  { value: 'true', label: 'Ja' },
  { value: 'false', label: 'Nein' }
];

const NO_VALUE_OPS = new Set(['is_empty', 'is_not_empty']);
const LIST_OPS = new Set(['in', 'not_in']);
const DATE_FIELDS = new Set(['doc_date', 'created_at', 'updated_at']);

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  mode: { type: String, default: 'create' },
  folder: { type: Object, default: null },
  tags: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  apiBaseUrl: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'close', 'save']);

const dialogOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const dialogTitle = computed(() => (props.mode === 'edit' ? 'Ordner bearbeiten' : 'Intelligenten Ordner erstellen'));
const dialogHeaderSubtitle = computed(() =>
  'Dieser Ordner aktualisiert sich automatisch anhand deiner Regeln.'
);
const dialogDescription = computed(() => '');

const matchOptions = [
  { value: 'AND', label: 'UND' },
  { value: 'OR', label: 'ODER' }
];

const fieldOptions = FIELD_OPTIONS;
const ocrStatusOptions = OCR_STATUS_OPTIONS;
const favoriteOptions = FAVORITE_OPTIONS;

const name = ref('');
const matchOp = ref('AND');
const rules = ref([createRule()]);
const editorError = ref('');
const preview = ref({
  loading: false,
  total: null,
  error: ''
});

const normalizedNameValue = computed(() => normalizeScalar(name.value));
const hasName = computed(() => normalizedNameValue.value.length > 0);
const previewDisplayTotal = computed(() =>
  typeof preview.value.total === 'number' && Number.isFinite(preview.value.total) ? String(preview.value.total) : '0'
);

const tagOptions = computed(() => {
  const values = (props.tags || []).map((tag) => String(tag?.name || '').trim()).filter(Boolean);
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, 'de-DE', { sensitivity: 'base' }));
});

const categoryOptions = computed(() => {
  const values = (props.categories || [])
    .map((category) => {
      if (typeof category === 'string') {
        return category.trim();
      }
      return String(category?.name || '').trim();
    })
    .filter(Boolean);
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, 'de-DE', { sensitivity: 'base' }));
});

let previewTimer = null;

function makeUiId(prefix) {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isNoValueOp(op) {
  return NO_VALUE_OPS.has(String(op || ''));
}

function isListOp(op) {
  return LIST_OPS.has(String(op || ''));
}

function isDateField(field) {
  return DATE_FIELDS.has(String(field || ''));
}

function listValueOptions(field) {
  if (field === 'tags') {
    return tagOptions.value;
  }
  if (field === 'category') {
    return categoryOptions.value;
  }
  return [];
}

function defaultOperatorForField(field) {
  const options = operatorOptions(field);
  return options.length > 0 ? options[0].value : 'contains';
}

function defaultValueForField(field, op) {
  if (field === 'is_favorite' && op === 'equals') {
    return 'true';
  }
  return '';
}

function createRule(seed = {}) {
  const field = FIELD_OPTIONS.some((item) => item.value === seed.field) ? seed.field : 'title';
  const opOptions = operatorOptions(field);
  const op = opOptions.some((item) => item.value === seed.op) ? seed.op : defaultOperatorForField(field);
  return {
    id: makeUiId('sf-rule'),
    field,
    op,
    value: String(seed.value ?? defaultValueForField(field, op)),
    values: Array.isArray(seed.values) ? seed.values.map((item) => String(item || '').trim()).filter(Boolean) : [],
    from: String(seed.from ?? ''),
    to: String(seed.to ?? '')
  };
}

function operatorOptions(field) {
  return OPERATOR_MAP[field] || OPERATOR_MAP.title;
}

function addRule() {
  rules.value = [...rules.value, createRule()];
}

function removeRule(ruleId) {
  if (rules.value.length <= 1) {
    return;
  }
  rules.value = rules.value.filter((rule) => rule.id !== ruleId);
}

function patchRule(ruleId, patch) {
  rules.value = rules.value.map((rule) => (rule.id === ruleId ? { ...rule, ...patch } : rule));
}

function setRuleField(ruleId, nextField) {
  const field = FIELD_OPTIONS.some((item) => item.value === nextField) ? nextField : 'title';
  const op = defaultOperatorForField(field);
  patchRule(ruleId, {
    field,
    op,
    value: defaultValueForField(field, op),
    values: [],
    from: '',
    to: ''
  });
}

function setRuleOp(ruleId, nextOp) {
  const current = rules.value.find((rule) => rule.id === ruleId);
  if (!current) {
    return;
  }
  const allowedOps = operatorOptions(current.field).map((item) => item.value);
  const op = allowedOps.includes(nextOp) ? nextOp : defaultOperatorForField(current.field);
  patchRule(ruleId, { op, value: defaultValueForField(current.field, op), values: [], from: '', to: '' });
}

function setRuleValue(ruleId, nextValue) {
  patchRule(ruleId, { value: String(nextValue ?? '').trim() });
}

function setRuleValues(ruleId, nextValues) {
  const values = Array.isArray(nextValues)
    ? nextValues.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  patchRule(ruleId, { values });
}

function setRuleRange(ruleId, key, nextValue) {
  if (key !== 'from' && key !== 'to') {
    return;
  }
  patchRule(ruleId, { [key]: String(nextValue ?? '').trim() });
}

function parseResponseError(response, fallbackMessage) {
  return response
    .json()
    .then((payload) => payload?.error?.message || fallbackMessage)
    .catch(() => fallbackMessage);
}

function normalizeScalar(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function normalizeList(values) {
  const seen = new Set();
  const normalized = [];
  for (const value of values || []) {
    const item = normalizeScalar(value);
    if (!item) {
      continue;
    }
    const key = item.toLocaleLowerCase('de-DE');
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push(item);
  }
  return normalized;
}

function buildQueryDefinition() {
  if (rules.value.length === 0) {
    throw new Error('Mindestens eine Regel ist erforderlich.');
  }

  const normalizedRules = rules.value.map((rule, index) => {
    const field = rule.field;
    const op = rule.op;
    if (!field || !op) {
      throw new Error(`Regel ${index + 1} ist unvollständig.`);
    }

    const base = { field, op };
    if (isNoValueOp(op)) {
      return base;
    }

    if (op === 'between') {
      const from = normalizeScalar(rule.from);
      const to = normalizeScalar(rule.to);
      if (!from || !to) {
        throw new Error(`Regel ${index + 1}: Bitte Von/Bis setzen.`);
      }
      return { ...base, value: { from, to } };
    }

    if (isListOp(op)) {
      const values = normalizeList(rule.values);
      if (values.length === 0) {
        throw new Error(`Regel ${index + 1}: Mindestens ein Wert erforderlich.`);
      }
      return { ...base, value: values };
    }

    if (field === 'is_favorite') {
      return { ...base, value: String(rule.value) === 'true' };
    }

    const scalarValue = normalizeScalar(rule.value);
    if (!scalarValue) {
      throw new Error(`Regel ${index + 1}: Wert fehlt.`);
    }
    return { ...base, value: scalarValue };
  });

  return {
    version: 1,
    group: {
      op: matchOp.value === 'OR' ? 'OR' : 'AND',
      rules: normalizedRules
    }
  };
}

function buildSavePayload() {
  return {
    name: normalizedNameValue.value,
    query_json: buildQueryDefinition()
  };
}

const hasDefinedRules = computed(() => {
  try {
    buildQueryDefinition();
    return true;
  } catch {
    return false;
  }
});

const isSaveDisabled = computed(() => !hasName.value || !hasDefinedRules.value);

async function runPreview() {
  if (!props.modelValue) {
    return;
  }

  let queryJson;
  try {
    queryJson = buildQueryDefinition();
    editorError.value = '';
  } catch (error) {
    preview.value = {
      loading: false,
      total: null,
      error: String(error?.message || 'Regeln sind unvollständig.')
    };
    return;
  }

  preview.value = {
    ...preview.value,
    loading: true,
    error: ''
  };

  try {
    const response = await fetch(`${props.apiBaseUrl}/api/smart-folders/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_json: queryJson,
        count_only: true
      })
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response, 'Treffer konnten nicht berechnet werden.'));
    }

    const payload = await response.json();
    preview.value = {
      loading: false,
      total: Number(payload?.total || 0),
      error: ''
    };
  } catch (error) {
    preview.value = {
      loading: false,
      total: null,
      error: String(error?.message || 'Treffer konnten nicht berechnet werden.')
    };
  }
}

function schedulePreview() {
  if (previewTimer) {
    window.clearTimeout(previewTimer);
  }
  previewTimer = window.setTimeout(() => {
    previewTimer = null;
    void runPreview();
  }, 300);
}

function hydrateFromFolder(folder) {
  editorError.value = '';
  preview.value = {
    loading: false,
    total: null,
    error: ''
  };

  name.value = normalizeScalar(folder?.name || '');
  matchOp.value = 'AND';
  let nextRules = [];

  const query = folder?.query_json;
  if (query && typeof query === 'object' && Number(query.version) === 1 && query.group && typeof query.group === 'object') {
    const group = query.group;
    matchOp.value = String(group.op || '').toUpperCase() === 'OR' ? 'OR' : 'AND';
    const rawRules = Array.isArray(group.rules) ? group.rules : [];
    nextRules = rawRules
      .filter((rule) => rule && typeof rule === 'object' && typeof rule.field === 'string' && typeof rule.op === 'string')
      .map((rule) => {
        if (rule.op === 'between' && rule.value && typeof rule.value === 'object') {
          return createRule({
            field: rule.field,
            op: rule.op,
            from: rule.value.from || '',
            to: rule.value.to || ''
          });
        }
        if (LIST_OPS.has(String(rule.op)) && Array.isArray(rule.value)) {
          return createRule({
            field: rule.field,
            op: rule.op,
            values: rule.value
          });
        }
        if (NO_VALUE_OPS.has(String(rule.op))) {
          return createRule({
            field: rule.field,
            op: rule.op
          });
        }
        return createRule({
          field: rule.field,
          op: rule.op,
          value: rule.value
        });
      });
  }

  rules.value = nextRules.length > 0 ? nextRules : [createRule()];
  schedulePreview();
}

function submit() {
  if (isSaveDisabled.value) {
    editorError.value = '';
    return;
  }

  try {
    const payload = buildSavePayload();
    editorError.value = '';
    emit('save', payload);
  } catch (error) {
    editorError.value = String(error?.message || 'Regeln sind unvollständig.');
  }
}

function handleClose() {
  emit('close');
}

function cancel() {
  dialogOpen.value = false;
  handleClose();
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      return;
    }
    hydrateFromFolder(props.folder);
  }
);

watch(
  () => props.folder,
  (folder) => {
    if (!props.modelValue) {
      return;
    }
    hydrateFromFolder(folder);
  },
  { deep: true }
);

watch(
  () => [name.value, matchOp.value, rules.value],
  () => {
    if (!props.modelValue) {
      return;
    }
    schedulePreview();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (previewTimer) {
    window.clearTimeout(previewTimer);
  }
});
</script>

<style scoped>
.sf-editor {
  display: grid;
  gap: 14px;
}

.sf-top-row {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 3fr);
  gap: 10px;
  align-items: start;
}

.sf-rules {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 14px;
  padding: 12px;
  display: grid;
  gap: 10px;
}

.sf-rules__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.85rem;
  font-weight: 600;
  opacity: 0.78;
}

.sf-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.sf-count__spinner {
  flex: 0 0 auto;
}

.sf-count--rules {
  margin-left: auto;
}

.sf-rules__list {
  display: grid;
  gap: 10px;
}

.sf-rule-row {
  display: grid;
  grid-template-columns: minmax(165px, 1fr) minmax(165px, 0.95fr) minmax(0, 1.8fr) auto;
  gap: 8px;
  align-items: start;
}

.sf-rule-row__value {
  min-width: 0;
}

.sf-rule-row__empty {
  min-height: 40px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.22);
  border-radius: 8px;
  font-size: 0.83rem;
  opacity: 0.75;
}

.sf-range {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.sf-add-btn {
  justify-self: flex-start;
}

.sf-rules__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sf-footer {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.sf-footer__actions {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 760px) {
  .sf-top-row {
    grid-template-columns: 1fr;
  }

  .sf-rule-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .sf-footer {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .sf-footer__actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .sf-rules__footer {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .sf-count--rules {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
