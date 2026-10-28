<template>
  <section v-list-reveal="{ selector: ':scope > ul > li', key: revealKey, ready: !loading }" class="document-section-card" :aria-label="label || title" :aria-busy="loading">
    <header class="document-section-card__header">
      <h3 class="document-section-card__heading">
        <span>{{ title }}</span>
        <span class="document-section-card__count">{{ count }}</span>
      </h3>
      <div v-if="$slots.actions" class="document-section-card__actions"><slot name="actions" /></div>
    </header>
    <div v-if="loading" class="document-section-card__state" role="status">
      <v-progress-circular indeterminate color="primary" size="18" width="2" :aria-label="loadingLabel || `${title} werden geladen`" />
      <span v-if="loadingLabel">{{ loadingLabel }}</span>
    </div>
    <div v-else-if="empty" class="document-section-card__empty">
      <span class="document-section-card__empty-icon" aria-hidden="true"><v-icon size="22">{{ emptyIcon || icon }}</v-icon></span>
      <strong>{{ emptyTitle }}</strong>
      <span>{{ emptyDescription }}</span>
    </div>
    <slot v-else />
  </section>
</template>
<script setup>
import { vListReveal } from '../directives/listReveal.js';
defineProps({
  title: { type: String, required: true }, label: String, icon: String,
  revealKey: { type: [String, Number], default: '' },
  count: { type: Number, default: 0 }, loading: Boolean, loadingLabel: String,
  empty: Boolean, emptyIcon: String, emptyTitle: String, emptyDescription: String
});
</script>
<style scoped>
.document-section-card { display: flex; flex-direction: column; gap: 12px; min-width: 0; margin-top: 16px; padding: 14px; border: 1px solid var(--pm-divider, #d8dfe1); border-radius: 14px; background: color-mix(in srgb, var(--pm-chip-bg, #eef2f4) 62%, transparent); }
.document-section-card__header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.document-section-card__heading { display: flex; align-items: center; gap: 8px; min-width: 0; margin: 0; color: var(--pm-text, #0e181b); font: inherit; font-size: .88rem; font-weight: 650; }
.document-section-card__count { flex: 0 0 auto; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 100px; background: color-mix(in srgb, var(--pm-muted, #535e62) 12%, transparent); color: var(--pm-muted, #535e62); font-size: .68rem; line-height: 20px; text-align: center; }
.document-section-card__actions { margin-left: auto; }
.document-section-card__state { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 8px; padding: 10px 0; color: var(--pm-muted); font-size: .76rem; }
.document-section-card__empty { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 14px 12px 16px; color: var(--pm-muted, #748084); text-align: center; font-size: .76rem; line-height: 1.55; }
.document-section-card__empty-icon { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; margin-bottom: 3px; border-radius: 11px; background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent); color: color-mix(in srgb, var(--pm-accent, #006b75) 78%, var(--pm-muted, #748084)); }
.document-section-card__empty strong { color: var(--pm-text, #0e181b); font-size: .84rem; font-weight: 600; }
.document-section-card__empty > span:last-child { max-width: 520px; }
</style>
