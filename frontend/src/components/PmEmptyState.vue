<template>
  <div class="pm-empty-state" :class="`pm-empty-state--${size}`">
    <v-icon
      class="pm-empty-state__icon"
      :icon="icon"
      :size="size === 'lg' ? 72 : 56"
    />
    <div class="pm-empty-state__body">
      <p class="pm-empty-state__title">{{ title }}</p>
      <p v-if="subtitle" class="pm-empty-state__subtitle">{{ subtitle }}</p>
      <div v-if="$slots.default" class="pm-empty-state__action">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon:     { type: String, required: true },
  title:    { type: String, required: true },
  subtitle: { type: String, default: '' },
  /** 'md' für Dokumentenliste, 'lg' für Vorschaubereich */
  size:     { type: String, default: 'md' },
});
</script>

<style scoped>
.pm-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 24px;
  width: 100%;
  height: 100%;
}

.pm-empty-state__icon {
  opacity: 0.38;
  flex-shrink: 0;
}

.pm-empty-state__body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  max-width: 280px;
}

.pm-empty-state__title {
  margin: 0;
  font-weight: 600;
  line-height: 1.3;
  color: rgb(var(--v-theme-on-surface));
}

.pm-empty-state--md .pm-empty-state__title { font-size: 0.94rem; }
.pm-empty-state--lg .pm-empty-state__title { font-size: 1.0rem; }

.pm-empty-state__subtitle {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgb(var(--v-theme-on-surface) / 0.55);
}

.pm-empty-state__action {
  margin-top: 8px;
}
</style>
