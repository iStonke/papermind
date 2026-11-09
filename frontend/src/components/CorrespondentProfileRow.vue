<template>
  <li class="corr-structure__row" :class="{ 'corr-structure__row--tile': tile }">
    <button type="button" class="corr-structure__link" @click="$emit('open')">
      <v-icon size="19" class="corr-structure__icon" aria-hidden="true">{{ icon }}</v-icon>
      <span class="corr-structure__copy">
        <strong :title="tile ? name : undefined">{{ name }}</strong>
        <span>{{ tile && countLabel ? `${subtitle} · ${countLabel}` : subtitle }}</span>
      </span>
      <span v-if="!tile && countLabel" class="corr-structure__count">{{ countLabel }}</span>
      <v-icon v-if="!tile" size="16" class="corr-structure__arrow" aria-hidden="true">mdi-chevron-right</v-icon>
    </button>
    <button
      type="button"
      class="corr-structure__remove"
      :disabled="disabled"
      :aria-label="removeLabel"
      :title="tile ? removeLabel : undefined"
      @click="$emit('remove')"
    ><v-icon size="14" aria-hidden="true">mdi-close</v-icon></button>
  </li>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  icon: { type: String, required: true },
  subtitle: { type: String, required: true },
  countLabel: { type: String, default: '' },
  removeLabel: { type: String, required: true },
  tile: Boolean,
  disabled: Boolean,
});

defineEmits(['open', 'remove']);
</script>

<style scoped>
.corr-structure__row { display: flex; align-items: center; gap: 4px; }
.corr-structure__link {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  min-height: 46px;
  padding: 6px 5px;
  border: 0;
  border-radius: 6px;
  background: none;
  color: var(--pm-muted);
  font: inherit;
  text-align: start;
  cursor: pointer;
}
.corr-structure__link:hover { background: var(--pm-row-hover); }
.corr-structure__link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -2px; }
.corr-structure__icon { grid-area: icon; color: var(--pm-accent-text); }
.corr-structure__copy { grid-area: copy; flex: 1; min-width: 0; overflow-wrap: anywhere; }
.corr-structure__copy strong { display: block; color: var(--pm-text); font-size: 0.89rem; font-weight: 500; }
.corr-structure__copy > span, .corr-structure__count { display: block; font-size: 0.76rem; }
.corr-structure__count { grid-area: count; flex: none; white-space: nowrap; font-variant-numeric: tabular-nums; }
.corr-structure__arrow { grid-area: arrow; }
.corr-structure__remove {
  flex: none;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: none;
  color: var(--pm-muted);
  cursor: pointer;
}
.corr-structure__remove:hover:not(:disabled) { background: var(--pm-row-hover); color: var(--pm-error); }

@container (max-width: 340px) {
  .corr-structure__link:has(.corr-structure__count) {
    display: grid;
    grid-template-columns: 19px minmax(0, 1fr) 16px;
    grid-template-areas: "icon copy arrow" "icon count arrow";
    gap: 0 9px;
  }
}

.corr-structure__row--tile {
  align-items: stretch;
  gap: 0;
  min-width: 0;
  padding: 3px;
  border: 1px solid var(--pm-list-divider);
  border-radius: 8px;
  background: var(--pm-app-surface);
}
.corr-structure__row--tile .corr-structure__link {
  display: grid;
  grid-template-columns: 19px minmax(0, 1fr);
  grid-template-areas: "icon copy";
  align-content: center;
  gap: 0 8px;
  min-height: 54px;
  padding: 7px 6px;
}
.corr-structure__row--tile .corr-structure__copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.corr-structure__row--tile .corr-structure__remove { align-self: flex-start; }
.corr-structure__row--tile .corr-structure__remove:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -2px; }

@media (pointer: coarse) {
  .corr-structure__remove { width: 44px; height: 44px; }
}
</style>
