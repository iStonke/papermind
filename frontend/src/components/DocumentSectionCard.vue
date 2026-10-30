<template>
  <section class="document-section-card" :class="{ 'document-section-card--empty': empty && !loading }" :aria-label="label || title" :aria-busy="loading">
    <header class="document-section-card__header">
      <h3 class="document-section-card__heading">
        <span>{{ title }}</span>
        <span v-if="count > 0" class="document-section-card__count">{{ count }}</span>
      </h3>
      <div v-if="$slots.actions" class="document-section-card__actions"><slot name="actions" /></div>
    </header>
    <slot name="toolbar" />
    <div v-if="loading" class="document-section-card__state" role="status">
      <v-progress-circular indeterminate color="primary" size="18" width="2" :aria-label="loadingLabel || `${title} werden geladen`" />
      <span v-if="loadingLabel">{{ loadingLabel }}</span>
    </div>
    <p v-else-if="empty" class="document-section-card__empty">{{ emptyMessage }}</p>
    <slot v-else />
  </section>
</template>
<script setup>
defineProps({
  title: { type: String, required: true }, label: String,
  count: { type: Number, default: 0 }, loading: Boolean, loadingLabel: String,
  empty: Boolean, emptyMessage: String
});
</script>
<style scoped>
.document-section-card { display: flex; flex-direction: column; gap: 12px; min-width: 0; margin-top: 16px; padding: 14px; border: 1px solid var(--pm-divider, #d8dfe1); border-radius: 14px; background: color-mix(in srgb, var(--pm-chip-bg, #eef2f4) 62%, transparent); }
.document-section-card--empty { gap:8px; background:transparent; border-color:color-mix(in srgb, var(--pm-divider, #d8dfe1) 70%, transparent); }
.document-section-card__header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.document-section-card__heading { display: flex; align-items: center; gap: 8px; min-width: 0; margin: 0; color: var(--pm-text, #0e181b); font: inherit; font-size: .88rem; font-weight: 650; }
.document-section-card__count { flex: 0 0 auto; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 100px; background: color-mix(in srgb, var(--pm-muted, #535e62) 12%, transparent); color: var(--pm-muted, #535e62); font-size: .68rem; line-height: 20px; text-align: center; }
.document-section-card__actions { margin-left: auto; }
.document-section-card__state { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 8px; padding: 10px 0; color: var(--pm-muted); font-size: .76rem; }
.document-section-card__empty { margin:0; color:var(--pm-muted, #748084); text-align:left; font-size:.76rem; line-height:1.55; }
</style>
