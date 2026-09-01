<!--
  GhostAddCard — anklickbare „Anlegen"-Ghost-Karte für Leerzustände. Sieht aus wie
  eine Geisterkarte (gestrichelt, gleiche Höhe), ist aber leicht teal getönt und
  trägt ein Plus-Icon + Hinweistext, um zum Anlegen einzuladen. Root = <button>,
  d. h. der Elternteil hört per @click.
-->
<template>
  <button type="button" class="gac">
    <span class="gac__icon" aria-hidden="true"><v-icon size="22">mdi-plus</v-icon></span>
    <span class="gac__title">{{ title }}</span>
    <span v-if="subtitle" class="gac__sub">{{ subtitle }}</span>
  </button>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
});
</script>

<style scoped>
.gac {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-height: 156px;
  padding: 16px;
  border: 1.5px dashed color-mix(in srgb, var(--pm-accent, #006b75) 42%, var(--pm-divider, #d8dfe1));
  border-radius: 12px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 5%, transparent);
  cursor: pointer;
  font: inherit;
  text-align: center;
  transition: background 130ms ease, border-color 130ms ease, transform 130ms ease, box-shadow 130ms ease;
}
.gac:hover {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
  border-color: var(--pm-accent, #006b75);
  transform: translateY(-2px);
  box-shadow: 0 8px 22px color-mix(in srgb, var(--pm-accent, #006b75) 20%, transparent);
}
.gac:active { transform: translateY(0); }
.gac:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--pm-accent, #006b75) 55%, transparent);
}
.gac__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin-bottom: 5px;
  border-radius: 50%;
  color: var(--pm-accent, #006b75);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 14%, transparent);
}
.gac__title { font-size: 0.9rem; font-weight: 620; color: var(--pm-text, #0e181b); }
.gac__sub { font-size: 0.76rem; color: var(--pm-accent-strong, #00555f); }

@media (prefers-reduced-motion: reduce) {
  .gac { transition: none; }
  .gac:hover { transform: none; }
}
</style>
