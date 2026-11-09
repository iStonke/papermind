<template>
  <BaseDialog :model-value="modelValue" title="Korrespondenten anlegen" :max-width="520" card-class="corr-create-dialog" :persistent="saving" :loading="saving"
    primary-text="Anlegen und auswählen" :primary-disabled="!valid || hasExactMatch || !store.isLoaded" @update:model-value="emit('update:modelValue', $event)" @primary="submit">
    <div class="isd-correspondent-form">
      <CorrespondentPersonNameFields v-if="kind === 'person'"
        v-model:first-name="personName.firstName" v-model:last-name="personName.lastName" :disabled="saving" autofocus @submit="submit" />
      <v-text-field v-else ref="input" v-model="name" label="Name" maxlength="120" variant="outlined" autofocus name="pm-correspondent-search" autocomplete="off" :disabled="saving" hide-details
        @keydown.enter.prevent="submit" />
      <CorrespondentLegalFormHint v-if="kind === 'organization'" v-model:keep="keepLegalForm" :name="namePayload.name" :disabled="saving" />
      <CorrespondentSuggestions v-if="modelValue" :matches="suggestions" :name="namePayload.name" :exact="hasExactMatch" :busy="saving" @use="useExisting" @alias="useExisting($event, true)" />
      <p v-if="!store.isLoaded" class="isd-correspondent-error" role="status">
        {{ store.isLoading ? 'Korrespondenten werden geprüft …' : 'Korrespondenten konnten nicht geladen werden.' }}
        <v-btn v-if="!store.isLoading" variant="text" size="small" @click="store.fetchCorrespondents()">Erneut versuchen</v-btn>
      </p>
      <v-select :model-value="kind" :items="kinds" label="Art" variant="outlined" :disabled="saving" hide-details @update:model-value="setKind" />
      <p v-if="error" class="isd-correspondent-error" role="alert">{{ error }}</p>
    </div>
  </BaseDialog>
</template>
<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import BaseDialog from './BaseDialog.vue';
import CorrespondentSuggestions from './CorrespondentSuggestions.vue';
import { findCorrespondentSuggestions } from '../utils/correspondentSuggestions.js';
import CorrespondentPersonNameFields from './CorrespondentPersonNameFields.vue';
import CorrespondentLegalFormHint from './CorrespondentLegalFormHint.vue';
import { legalFormShortName } from '../utils/legalForms.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { personNameParts, personNamePayload, validCorrespondentName } from '../utils/correspondentPersonName.js';
const props = defineProps({ modelValue: Boolean, initialName: String });
const emit = defineEmits(['update:modelValue', 'created']);
const store = useCorrespondentStore();
const input = ref(null);
const name = ref('');
const personName = ref(personNameParts({}));
const kind = ref('organization');
const saving = ref(false);
const keepLegalForm = ref(false);
const error = ref('');
const kinds = [{ title:'Organisation', value:'organization' }, { title:'Person', value:'person' }, { title:'Sammlung', value:'collection' }];
const namePayload = computed(() => kind.value === 'person'
  ? personNamePayload(personName.value)
  : { name: name.value.replace(/\s+/gu, ' ').trim() });
const suggestions = computed(() => findCorrespondentSuggestions(store.correspondents, namePayload.value.name));
const hasExactMatch = computed(() => suggestions.value.some(match => match.exact));
const valid = computed(() => validCorrespondentName(namePayload.value.name));
watch(() => props.modelValue, async open => {
  if (!open) return;
  name.value = props.initialName || '';
  personName.value = personNameParts({});
  kind.value = 'organization';
  keepLegalForm.value = false;
  error.value = '';
  await store.ensureLoaded();
  await nextTick();
  input.value?.focus();
});
function setKind(nextKind) {
  if (kind.value === nextKind) return;
  const fullName = personNamePayload(personName.value).name;
  if (kind.value === 'person') name.value = fullName;
  if (nextKind === 'person' && name.value !== fullName) personName.value = personNameParts({ name: name.value });
  kind.value = nextKind;
}
async function useExisting(id, addAlias = false) {
  if (saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    if (addAlias && !(await store.addAlias(id, namePayload.value.name))?.ok) return;
    emit('created', id);
    emit('update:modelValue', false);
  } catch { error.value = 'Die Schreibweise konnte nicht gespeichert werden. Bitte erneut versuchen.'; }
  finally { saving.value = false; }
}
async function submit() {
  if (!valid.value || saving.value || hasExactMatch.value || !store.isLoaded) return;
  saving.value = true;
  error.value = '';
  try {
    const { name: fullName, ...nameParts } = namePayload.value;
    const existing = store.findByName(fullName);
    const result = existing ? { ok:true, id:existing.id } : await store.createCorrespondentByName(fullName, { kind:kind.value, ...nameParts,
      short_name: kind.value === 'organization' ? legalFormShortName(fullName, keepLegalForm.value) : undefined });
    if (result.ok && result.id) { emit('created', result.id); emit('update:modelValue', false); }
  } catch { error.value = 'Der Korrespondent konnte nicht angelegt werden. Bitte erneut versuchen.'; }
  finally { saving.value = false; }
}
</script>
<style scoped>
.isd-correspondent-form { display:flex; flex-direction:column; gap:12px; }
.isd-correspondent-error { color:rgb(var(--v-theme-error)); font-size:13px; margin:0; }
</style>
