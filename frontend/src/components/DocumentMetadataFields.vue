<template>
  <div class="pm-metadata-fields">
    <div v-for="field in fields" :key="field.key" class="pm-metadata-row" :class="{ 'pm-metadata-row--ai': sources[field.key] }" :data-field="field.key" :data-drawer-expand-boundary="field.key === 'note' ? '' : undefined">
      <label :for="`${id}-${field.key}`" class="pm-metadata-label">{{ field.label }}</label>
      <v-chip v-if="sources[field.key]" class="pm-metadata-ai-chip" size="x-small" color="primary"
        variant="tonal" rounded="pill" :ripple="false" title="Von der KI erkannt" aria-label="Von der KI erkannt">
        <v-icon start size="12" aria-hidden="true">mdi-creation</v-icon>KI
      </v-chip>
      <div class="pm-metadata-value">
        <div class="pm-metadata-control" :class="{ 'pm-metadata-control--error': Boolean(errors[field.key]) }">
          <v-text-field v-if="field.key === 'name'" :id="`${id}-name`" :model-value="name" maxlength="200"
            :required="requiredFields" :aria-describedby="errors.name ? `${id}-name-error` : undefined"
            class="pm-name-field" variant="plain" density="compact" hide-details :placeholder="pending.name ? 'Wird ermittelt…' : 'Dokumentname…'" :disabled="disabled"
            :error="Boolean(errors.name)" :aria-invalid="Boolean(errors.name)" @update:model-value="emit('update:name', $event)" @blur="emit('text-blur')" />
          <v-text-field v-else-if="field.key === 'date'" :id="`${id}-date`" :model-value="date" maxlength="10"
            :required="requiredFields" :aria-describedby="errors.date ? `${id}-date-error` : undefined"
            class="pm-date-field" variant="plain" density="compact" hide-details :placeholder="pending.date ? 'Wird ermittelt…' : 'TT.MM.JJJJ'" inputmode="numeric" :disabled="disabled"
            :error="Boolean(errors.date)" :aria-invalid="Boolean(errors.date)" @update:model-value="emit('update:date', $event)" @blur="emit('date-blur')" @keydown="emit('date-keydown', $event)" />
          <v-select v-else-if="field.key === 'category'" :id="`${id}-category`" :model-value="category" :items="categories"
            :required="requiredFields" :error="Boolean(errors.category)" :aria-invalid="Boolean(errors.category)" :aria-describedby="errors.category ? `${id}-category-error` : undefined"
            variant="plain" density="compact" hide-details clearable :placeholder="pending.category ? 'Wird ermittelt…' : 'Dokumenttyp wählen…'" :disabled="disabled"
            :loading="categoryLoading" :menu-props="menuProps" @update:model-value="emit('update:category', $event)" />
          <v-autocomplete v-else-if="field.key === 'correspondent'" :id="`${id}-correspondent`" :model-value="correspondent"
            :required="requiredFields" :error="Boolean(errors.correspondent)" :aria-invalid="Boolean(errors.correspondent)" :aria-describedby="errors.correspondent ? `${id}-correspondent-error` : undefined"
            :items="correspondents" item-title="title" item-value="value" :return-object="false" variant="plain" density="compact"
            hide-details clearable :placeholder="pending.correspondent ? 'Wird ermittelt…' : 'Korrespondent wählen…'" :disabled="disabled" :loading="correspondentLoading"
            :menu-props="menuProps" @update:model-value="emit('update:correspondent', $event)" @blur="emit('correspondent-blur')" @focus="emit('correspondent-focus')">
            <template #item="{ props: itemProps, item }"><v-list-item v-bind="itemProps" :title="undefined" :prepend-icon="undefined">
              <template #title>{{ item.raw?.name || item.title }}{{ item.raw?.kind === 'collection' ? ' · Sammlung' : '' }}</template>
            </v-list-item></template>
            <template #selection="{ item }">{{ item.raw?.short_name || item.raw?.name || item.title }}{{ item.raw?.kind === 'collection' ? ' · Sammlung' : '' }}</template>
            <template #no-data><v-list-item title="Kein Korrespondent gefunden" subtitle="Neue Korrespondenten in den Einstellungen anlegen" /></template>
          </v-autocomplete>
          <template v-else-if="field.key === 'tags'"><slot name="tags" :input-id="`${id}-tags`" :required="requiredFields" :error="Boolean(errors.tags)" :error-id="errors.tags ? `${id}-tags-error` : undefined" /></template>
          <v-textarea v-else :id="`${id}-note`" :model-value="note" maxlength="10000" :rows="3" :max-rows="8" auto-grow
            variant="plain" density="compact" hide-details :placeholder="pending.note ? 'Wird ermittelt…' : 'Notiz hinzufügen…'" :disabled="disabled"
            :error="Boolean(errors.note)" :aria-invalid="Boolean(errors.note)" @update:model-value="emit('update:note', $event)" @blur="emit('text-blur')" />
          <v-btn v-if="manage && ['category', 'correspondent'].includes(field.key)" icon="mdi-cog-outline" variant="text" size="x-small"
            :aria-label="field.key === 'category' ? 'Dokumenttypen verwalten' : 'Korrespondenten verwalten'" @click="emit(`manage-${field.key}`)" />
        </div>
        <p v-if="errors[field.key]" :id="`${id}-${field.key}-error`" class="pm-metadata-error" role="alert">{{ errors[field.key] }}</p>
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
  pending: { type: Object, default: () => ({}) },
  menuProps: { type: Object, default: () => ({ maxHeight: 240, attach: 'body', zIndex: 6000 }) },
  disabled: Boolean, categoryLoading: Boolean, correspondentLoading: Boolean, requiredFields: Boolean, manage: Boolean });
const emit = defineEmits(['update:name', 'update:date', 'update:category', 'update:correspondent', 'update:note',
  'text-blur', 'date-blur', 'date-keydown', 'correspondent-blur', 'correspondent-focus', 'manage-category', 'manage-correspondent']);
const id = useId();
const fields = [{ key: 'name', label: 'Dokumentname' }, { key: 'date', label: 'Dokumentdatum' },
  { key: 'category', label: 'Dokumenttyp' }, { key: 'correspondent', label: 'Korrespondent' },
  { key: 'tags', label: 'Tags' }, { key: 'note', label: 'Notizen' }];
</script>
<style scoped>
.pm-metadata-fields { display: grid; gap: 16px; min-width: 0; }
.pm-metadata-row { display: grid; grid-template-columns: 114px minmax(0, 1fr); grid-template-areas: 'label value'; gap: 12px; align-items: start; }
.pm-metadata-row--ai { grid-template-areas: '. source' 'label value'; row-gap: 4px; }
.pm-metadata-label { grid-area: label; color: var(--pm-muted, #687076); font-size: 12px; padding-top: 12px; }
.pm-metadata-value { grid-area: value; min-width: 0; }
.pm-metadata-control { display: flex; align-items: center; min-width: 0; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; background: rgba(var(--v-theme-on-surface), .035); }
.pm-metadata-control:hover { border-color: rgba(var(--v-theme-on-surface), .18); }
.pm-metadata-control:focus-within { border-color: rgb(var(--v-theme-primary)); }
.pm-metadata-control.pm-metadata-control--error { border-color: rgb(var(--v-theme-error)); }
.pm-metadata-control > * { min-width: 0; }
.pm-metadata-control :deep(.v-field__input) { padding-top: 7px; padding-bottom: 7px; font-size: 14px; min-height: 36px; }
.pm-metadata-error { margin: 4px 0 0; color: rgb(var(--v-theme-error)); font-size: 12px; }
.pm-metadata-ai-chip.v-chip { grid-area: source; align-self: center; justify-self: end; height: 20px; padding-inline: 7px; border: 1px solid rgba(var(--v-theme-primary), .18); font-size: 10px; font-weight: 600; letter-spacing: .025em; }
@container (max-width: 420px) {
  .pm-metadata-row { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: 'label label' 'value value'; gap: 4px 8px; }
  .pm-metadata-row--ai { grid-template-areas: 'label source' 'value value'; }
  .pm-metadata-label { align-self: center; line-height: 20px; padding-top: 0; }
}
</style>
