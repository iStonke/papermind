<!--
  PmListHeader — Standard-Kopfzeile eines Listenbereichs, wie in der
  Dokumentenliste: Titel (+ Zählzeile), Suchfeld mit optionalem Bereichsfilter,
  rechts Ansichtsumschalter und „Neu“-Button als kompakte Tonal-Iconbuttons.
  Beim Fokus der Suche weicht der Titel, damit das Feld die volle Breite hat.
  Darunter gehört die gemeinsame Filter-/Sortierleiste ListActionToolbar.

  Optik in theme/listHeader.css (global, damit spätere Bereiche sie ohne
  eigene Kopie nutzen). Weitere Aktionen über den Slot `actions`, zusätzliche
  Zeilen unter dem Titel über den Slot `subtitle`.
-->
<template>
  <header class="pm-list-header" :class="{ 'pm-list-header--search-focused': isSearchFocused }">
    <div class="pm-list-header__title">
      <div class="pm-list-header__heading">{{ title }}</div>
      <slot name="subtitle">
        <div v-if="subtitle" class="pm-list-header__sub">{{ subtitle }}</div>
      </slot>
    </div>

    <div
      class="pm-searchbar pm-searchbar--header"
      :class="{ 'pm-searchbar--filled': !!search, 'pm-searchbar--scoped': searchScopes.length && searchScope !== searchScopes[0]?.value }"
      role="search"
      @focusin="isSearchFocused = true"
      @focusout="onSearchFocusOut"
    >
      <v-text-field
        ref="searchFieldRef"
        :model-value="search"
        class="pm-searchbar__field"
        prepend-inner-icon="mdi-magnify"
        clearable
        :placeholder="searchPlaceholder"
        :aria-label="searchLabel"
        density="compact"
        variant="plain"
        hide-details
        @update:model-value="emit('update:search', $event || '')"
        @keydown.esc="onSearchEscape"
      />
      <template v-if="searchScopes.length">
        <span class="pm-searchbar__divider" aria-hidden="true" />
        <v-menu location="bottom end" offset="6">
          <template #activator="{ props: menuProps }">
            <button
              v-bind="menuProps"
              type="button"
              class="pm-searchbar__scope"
              :aria-label="`Suchfeld: ${activeScope.label}`"
              :title="`Suchen in: ${activeScope.label}`"
            >
              <v-icon size="15" class="pm-searchbar__scope-icon">{{ activeScope.icon || 'mdi-file-search-outline' }}</v-icon>
              <span class="pm-searchbar__scope-label">{{ activeScope.label }}</span>
              <v-icon size="14" class="pm-searchbar__scope-chevron">mdi-chevron-down</v-icon>
            </button>
          </template>
          <v-list class="pm-menu pm-searchbar__menu" density="compact">
            <v-list-subheader>Suchen in</v-list-subheader>
            <v-list-item
              v-for="option in searchScopes"
              :key="option.value"
              :title="option.label"
              :prepend-icon="option.icon"
              :active="searchScope === option.value"
              @click="emit('update:searchScope', option.value)"
            >
              <template v-if="searchScope === option.value" #append>
                <v-icon size="16">mdi-check</v-icon>
              </template>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
    </div>

    <div v-if="$slots.actions || viewModes.length || createLabel" class="pm-list-header__actions">
      <slot name="actions" />
      <PmViewModeMenu
        v-if="viewModes.length > 1"
        :options="viewModes"
        :model-value="viewMode"
        @update:model-value="emit('update:viewMode', $event)"
      />
      <v-btn
        v-if="createLabel"
        class="list-header-btn pm-header-icon-btn"
        color="primary"
        variant="tonal"
        icon
        :aria-label="createLabel"
        :title="createLabel"
        @click="emit('create')"
      >
        <v-icon size="20">mdi-plus</v-icon>
      </v-btn>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue';
import PmViewModeMenu from './PmViewModeMenu.vue';

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  search: { type: String, default: '' },
  searchPlaceholder: { type: String, default: 'Suchen …' },
  searchLabel: { type: String, default: 'Liste durchsuchen' },
  /** Optionaler Bereichsfilter der Suche: [{ value, label, icon }]; erster Eintrag = ungefiltert. */
  searchScopes: { type: Array, default: () => [] },
  searchScope: { type: String, default: null },
  /** Darstellungen für den Umschalter: [{ value, label, icon }]; ab zwei Einträgen sichtbar. */
  viewModes: { type: Array, default: () => [] },
  viewMode: { type: String, default: null },
  /** Beschriftung (aria/Tooltip) des Plus-Buttons; leer = kein Button. */
  createLabel: { type: String, default: '' },
});
const emit = defineEmits(['update:search', 'update:searchScope', 'update:viewMode', 'create']);

const isSearchFocused = ref(false);
const searchFieldRef = ref(null);

const activeScope = computed(
  () => props.searchScopes.find((o) => o.value === props.searchScope) || props.searchScopes[0] || { label: '' }
);

function onSearchFocusOut(event) {
  // Menü des Bereichsfilters zählt nicht als Verlassen.
  isSearchFocused.value = event.currentTarget.contains(event.relatedTarget);
}

function onSearchEscape() {
  if (props.search) emit('update:search', '');
  else searchFieldRef.value?.blur?.();
}

defineExpose({
  focusSearch: () => searchFieldRef.value?.focus?.(),
});
</script>
