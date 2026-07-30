<template>
  <div class="pm-empty-state" :class="`pm-empty-state--${size}`">
    <div class="pm-empty-state__illustration" aria-hidden="true">
      <span class="pm-empty-state__halo" />
      <v-icon
        class="pm-empty-state__icon"
        :icon="icon"
        :size="size === 'lg' ? 72 : 56"
      />
    </div>
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
  animation: pm-empty-state-enter var(--pm-duration-normal, 210ms) var(--pm-easing-decel, ease-out) both;
}

.pm-empty-state__illustration {
  position: relative;
  display: grid;
  place-items: center;
  width: 88px;
  height: 88px;
  animation: pm-empty-state-illustration-enter 320ms var(--pm-easing-decel, ease-out) 70ms both;
}

.pm-empty-state__halo {
  position: absolute;
  inset: 6px;
  border: 1px solid color-mix(in srgb, var(--pm-accent, currentColor) 28%, transparent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--pm-accent, currentColor) 7%, transparent);
}

.pm-empty-state__icon {
  opacity: 0.38;
  flex-shrink: 0;
  z-index: 1;
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

@keyframes pm-empty-state-enter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes pm-empty-state-illustration-enter {
  from { opacity: 0; transform: translateY(4px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

:global(.pm-no-animations) .pm-empty-state,
:global(.pm-no-animations) .pm-empty-state__illustration {
  animation: none;
}

@media (prefers-reduced-motion: reduce) {
  .pm-empty-state,
  .pm-empty-state__illustration {
    animation: none;
  }
}
</style>
