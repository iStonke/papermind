<template>
  <div class="pm-metadata-fields">
    <div v-for="field in fields" :key="field.key" class="pm-metadata-row" :data-field="field.key" :data-drawer-expand-boundary="field.key === 'note' ? '' : undefined">
      <label :for="`${id}-${field.key}`" class="pm-metadata-label">{{ field.label }}{{ field.key === 'name' && requiredName ? ' *' : '' }}</label>
      <div class="pm-metadata-value">
        <div class="pm-metadata-control">
          <v-text-field v-if="field.key === 'name'" :id="`${id}-name`" :model-value="name" maxlength="200"
            class="pm-name-field" variant="plain" density="compact" hide-details placeholder="Dokumentname…" :disabled="disabled"
            :error="Boolean(errors.name)" @update:model-value="emit('update:name', $event)" @blur="emit('text-blur')" />
          <v-text-field v-else-if="field.key === 'date'" :id="`${id}-date`" :model-value="date" maxlength="10"
            class="pm-date-field" variant="plain" density="compact" hide-details placeholder="TT.MM.JJJJ" inputmode="numeric" :disabled="disabled"
            :error="Boolean(errors.date)" @update:model-value="emit('update:date', $event)" @blur="emit('date-blur')" @keydown="emit('date-keydown', $event)" />
          <v-select v-else-if="field.key === 'category'" :id="`${id}-category`" :model-value="category" :items="categories"
            variant="plain" density="compact" hide-details clearable placeholder="Dokumenttyp wählen…" :disabled="disabled"
            :loading="categoryLoading" :menu-props="menuProps" @update:model-value="emit('update:category', $event)" />
          <v-autocomplete v-else-if="field.key === 'correspondent'" :id="`${id}-correspondent`" :model-value="correspondent"
            :items="correspondents" item-title="title" item-value="value" :return-object="false" variant="plain" density="compact"
            hide-details clearable placeholder="Korrespondent wählen…" :disabled="disabled" :loading="correspondentLoading"
            :menu-props="menuProps" @update:model-value="emit('update:correspondent', $event)" @blur="emit('correspondent-blur')" @focus="emit('correspondent-focus')">
            <template #item="{ props: itemProps, item }"><v-list-item v-bind="itemProps" :title="undefined" :prepend-icon="undefined">
              <template #title>{{ item.raw?.name || item.title }}{{ item.raw?.kind === 'collection' ? ' · Sammlung' : '' }}</template>
            </v-list-item></template>
            <template #selection="{ item }">{{ item.raw?.short_name || item.raw?.name || item.title }}{{ item.raw?.kind === 'collection' ? ' · Sammlung' : '' }}</template>
            <template #no-data><v-list-item title="Kein Korrespondent gefunden" subtitle="Neue Korrespondenten in den Einstellungen anlegen" /></template>
          </v-autocomplete>
          <template v-else-if="field.key === 'tags'"><slot name="tags" /></template>
          <v-textarea v-else :id="`${id}-note`" :model-value="note" maxlength="10000" :rows="3" :max-rows="8" auto-grow
            variant="plain" density="compact" hide-details placeholder="Notiz hinzufügen…" :disabled="disabled"
            :error="Boolean(errors.note)" @update:model-value="emit('update:note', $event)" @blur="emit('text-blur')" />
          <v-btn v-if="manage && ['category', 'correspondent'].includes(field.key)" icon="mdi-cog-outline" variant="text" size="x-small"
            :aria-label="field.key === 'category' ? 'Dokumenttypen verwalten' : 'Korrespondenten verwalten'" @click="emit(`manage-${field.key}`)" />
        </div>
        <span v-if="sources[field.key]" class="pm-metadata-source">{{ sources[field.key] }}</span>
        <p v-if="errors[field.key]" class="pm-metadata-error" role="alert">{{ errors[field.key] }}</p>
        <slot :name="`after-${field.key}`" />
      </div>
    </div>
  </div>
</template>
<script setup>
import { useId } from 'vue';
defineProps({ name: String, date: String, category: String, correspondent: [String, Object], note: String,
  categories: { type: Array, default: () => [] }, correspondents: { type: Array, default: () => [] },
  errors: { type: Object, default: () => ({}) }, sources: { type: Object, default: () => ({}) },
  menuProps: { type: Object, default: () => ({ maxHeight: 240, attach: 'body', zIndex: 6000 }) },
  disabled: Boolean, categoryLoading: Boolean, correspondentLoading: Boolean, requiredName: Boolean, manage: Boolean });
const emit = defineEmits(['update:name', 'update:date', 'update:category', 'update:correspondent', 'update:note',
  'text-blur', 'date-blur', 'date-keydown', 'correspondent-blur', 'correspondent-focus', 'manage-category', 'manage-correspondent']);
const id = useId();
const fields = [{ key: 'name', label: 'Dokumentname' }, { key: 'date', label: 'Dokumentdatum' },
  { key: 'category', label: 'Dokumenttyp' }, { key: 'correspondent', label: 'Korrespondent' },
  { key: 'tags', label: 'Tags' }, { key: 'note', label: 'Notizen' }];
</script>
<style scoped>
.pm-metadata-fields { display: grid; gap: 10px; min-width: 0; }
.pm-metadata-row { display: grid; grid-template-columns: 114px minmax(0, 1fr); gap: 12px; align-items: start; }
.pm-metadata-label { color: var(--pm-muted, #687076); font-size: 12px; padding-top: 12px; }
.pm-metadata-value { min-width: 0; }
.pm-metadata-control { display: flex; align-items: center; min-width: 0; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; background: rgba(var(--v-theme-on-surface), .035); }
.pm-metadata-control:hover { border-color: rgba(var(--v-theme-on-surface), .18); }
.pm-metadata-control:focus-within { border-color: rgb(var(--v-theme-primary)); }
.pm-metadata-control > * { min-width: 0; }
.pm-metadata-control :deep(.v-field__input) { padding-top: 7px; padding-bottom: 7px; font-size: 14px; min-height: 36px; }
.pm-metadata-error { margin: 4px 0 0; color: rgb(var(--v-theme-error)); font-size: 12px; }
.pm-metadata-source { display: block; font-size: 11px; color: var(--pm-muted, #687076); margin-top: 3px; }
@container (max-width: 420px) { .pm-metadata-row { grid-template-columns: 1fr; gap: 3px; } .pm-metadata-label { padding-top: 2px; } }
</style>
