<template>
  <BaseDialog :model-value="modelValue" title="Korrespondenten anlegen" :max-width="440" :persistent="saving" :loading="saving"
    primary-text="Anlegen und auswählen" :primary-disabled="!valid" @update:model-value="emit('update:modelValue', $event)" @primary="submit">
    <v-text-field ref="input" v-model="name" label="Name" maxlength="120" variant="outlined" autofocus :disabled="saving" hide-details
      @keydown.enter.prevent="submit" />
    <v-select v-model="kind" :items="kinds" label="Art" variant="outlined" :disabled="saving" hide-details class="mt-4" />
    <p v-if="error" class="isd-correspondent-error" role="alert">{{ error }}</p>
  </BaseDialog>
</template>
<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import BaseDialog from './BaseDialog.vue';
import { useCorrespondentStore } from '../stores/correspondents.js';
const props = defineProps({ modelValue: Boolean, initialName: String });
const emit = defineEmits(['update:modelValue', 'created']);
const store = useCorrespondentStore();
const input = ref(null);
const name = ref('');
const kind = ref('organization');
const saving = ref(false);
const error = ref('');
const kinds = [{ title:'Organisation', value:'organization' }, { title:'Person', value:'person' }, { title:'Sammlung', value:'collection' }];
const normalized = computed(() => name.value.replace(/\s+/gu, ' ').trim());
const valid = computed(() => normalized.value.length >= 2 && normalized.value.length <= 120);
watch(() => props.modelValue, async open => { if (open) { name.value = props.initialName || ''; kind.value = 'organization'; error.value = ''; await nextTick(); input.value?.focus(); } });
async function submit() {
  if (!valid.value || saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    const existing = store.findByName(normalized.value);
    const result = existing ? { ok:true, id:existing.id } : await store.createCorrespondentByName(normalized.value, { kind:kind.value });
    if (result.ok && result.id) { emit('created', result.id); emit('update:modelValue', false); }
  } catch { error.value = 'Der Korrespondent konnte nicht angelegt werden. Bitte erneut versuchen.'; }
  finally { saving.value = false; }
}
</script>
<style scoped>
.isd-correspondent-error { color:rgb(var(--v-theme-error)); font-size:13px; margin:12px 0 0; }
</style>
