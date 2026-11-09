<!--
  PmViewModeMenu — Ansichtsumschalter für Bereichskopfzeilen: kompakter
  Tonal-Iconbutton (zeigt das Symbol der aktiven Darstellung) mit Menü
  „Darstellung“. Optik in theme/listHeader.css (.document-viewmode-menu), damit
  Dokumente und alle übrigen Listen denselben Umschalter zeigen.
-->
<template>
  <v-menu location="bottom end" :offset="8" transition="fade-transition">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        class="list-header-viewmode pm-header-icon-btn"
        color="primary"
        variant="tonal"
        icon
        :aria-label="`${label}: ${activeOption.label}. Ändern`"
        :title="`${label}: ${activeOption.label}`"
      >
        <v-icon size="20">{{ activeOption.icon }}</v-icon>
      </v-btn>
    </template>
    <v-list class="pm-menu document-viewmode-menu" density="compact" min-width="196" role="menu" :aria-label="label">
      <div class="document-viewmode-menu__label">{{ label }}</div>
      <v-list-item
        v-for="option in options"
        :key="option.value"
        class="document-viewmode-menu__item"
        :class="{ 'document-viewmode-menu__item--active': modelValue === option.value }"
        :ripple="false"
        role="menuitemradio"
        :aria-checked="modelValue === option.value ? 'true' : 'false'"
        @click="emit('update:modelValue', option.value)"
      >
        <template #prepend>
          <span class="document-viewmode-menu__icon" aria-hidden="true">
            <v-icon size="17">{{ option.icon }}</v-icon>
          </span>
        </template>
        <v-list-item-title>{{ option.label }}</v-list-item-title>
        <template #append>
          <span class="document-viewmode-menu__check" aria-hidden="true">
            <v-icon v-if="modelValue === option.value" size="15">mdi-check</v-icon>
          </span>
        </template>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  /** [{ value, label, icon }] */
  options: { type: Array, required: true },
  modelValue: { type: String, default: null },
  label: { type: String, default: 'Darstellung' },
});
const emit = defineEmits(['update:modelValue']);

const activeOption = computed(
  () => props.options.find((o) => o.value === props.modelValue) || props.options[0] || { label: '', icon: 'mdi-format-list-bulleted' }
);
</script>
