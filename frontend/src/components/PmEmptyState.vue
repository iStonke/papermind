<template>
  <div class="pm-empty-state" :class="[`pm-empty-state--${size}`, { 'pm-empty-state--static': !animated }]">
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
  /** Auftritts-Animation. Ausschalten, wenn parallel ein anderer Platzhalter
   *  animiert (z. B. Vorschau-Platzhalter neben leerer Dokumentenliste). */
  animated: { type: Boolean, default: true },
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
  animation: pm-empty-state-fade 300ms var(--pm-easing, ease) both;
}

.pm-empty-state__illustration {
  position: relative;
  display: grid;
  place-items: center;
  width: 88px;
  height: 88px;
  /* Feder-Pop mit Overshoot und kleinem Dreh-Wackler beim Erscheinen. */
  animation: pm-empty-state-pop 640ms cubic-bezier(0.34, 1.56, 0.64, 1) 80ms both;
}

.pm-empty-state__halo {
  position: absolute;
  inset: 6px;
  border: 1px solid color-mix(in srgb, var(--pm-accent, currentColor) 28%, transparent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--pm-accent, currentColor) 7%, transparent);
}

/* Ein Akzent-Ring pulsiert einmalig aus dem Halo heraus. */
.pm-empty-state__halo::after {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 50%;
  border: 1.5px solid color-mix(in srgb, var(--pm-accent, currentColor) 48%, transparent);
  animation: pm-empty-state-halo-pulse 900ms var(--pm-easing-decel, ease-out) 260ms both;
}

.pm-empty-state__icon {
  opacity: 0.38;
  flex-shrink: 0;
  z-index: 1;
  /* Sanftes Dauer-Schweben nach dem Einfliegen – gibt dem Platzhalter Leben. */
  animation: pm-empty-state-float 4.5s ease-in-out 760ms infinite;
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
  animation: pm-empty-state-rise 440ms var(--pm-easing-decel, ease-out) 240ms both;
}

.pm-empty-state--md .pm-empty-state__title { font-size: 0.94rem; }
.pm-empty-state--lg .pm-empty-state__title { font-size: 1.0rem; }

.pm-empty-state__subtitle {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgb(var(--v-theme-on-surface) / 0.55);
  animation: pm-empty-state-rise 440ms var(--pm-easing-decel, ease-out) 320ms both;
}

.pm-empty-state__action {
  margin-top: 8px;
  animation: pm-empty-state-rise 440ms var(--pm-easing-decel, ease-out) 400ms both;
}

@keyframes pm-empty-state-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes pm-empty-state-pop {
  0%   { opacity: 0; transform: scale(0.4) rotate(-9deg); }
  55%  { opacity: 1; transform: scale(1.1) rotate(4deg); }
  75%  { transform: scale(0.96) rotate(-2deg); }
  100% { opacity: 1; transform: scale(1) rotate(0); }
}

@keyframes pm-empty-state-halo-pulse {
  0%   { opacity: 0.75; transform: scale(0.72); }
  100% { opacity: 0; transform: scale(1.95); }
}

@keyframes pm-empty-state-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}

@keyframes pm-empty-state-rise {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Auftritts-Animation komplett aus (animated=false) – z. B. Vorschau-Platzhalter,
   damit neben der leeren Dokumentenliste nur EIN Platzhalter animiert. */
.pm-empty-state--static,
.pm-empty-state--static .pm-empty-state__illustration,
.pm-empty-state--static .pm-empty-state__halo::after,
.pm-empty-state--static .pm-empty-state__icon,
.pm-empty-state--static .pm-empty-state__title,
.pm-empty-state--static .pm-empty-state__subtitle,
.pm-empty-state--static .pm-empty-state__action {
  animation: none;
}

:global(.pm-no-animations) .pm-empty-state,
:global(.pm-no-animations) .pm-empty-state__illustration,
:global(.pm-no-animations) .pm-empty-state__halo::after,
:global(.pm-no-animations) .pm-empty-state__icon,
:global(.pm-no-animations) .pm-empty-state__title,
:global(.pm-no-animations) .pm-empty-state__subtitle,
:global(.pm-no-animations) .pm-empty-state__action {
  animation: none;
}

@media (prefers-reduced-motion: reduce) {
  .pm-empty-state,
  .pm-empty-state__illustration,
  .pm-empty-state__halo::after,
  .pm-empty-state__icon,
  .pm-empty-state__title,
  .pm-empty-state__subtitle,
  .pm-empty-state__action {
    animation: none;
  }
}
</style>
