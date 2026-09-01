<!--
  VorlagenCard — einheitliche, grafische Karte für BEIDE Vorlagen-Arten:
  eine Mini-Vorschau (Schnellblock = kleine Abbildung der farbigen Feldbox,
  Startnotiz = Notiz-Seite), darunter farbiger Icon-Chip + Titel. Aktionen sind
  Icon-Buttons, die bei Hover erscheinen (statt Textlinks). Rein präsentational.
-->
<template>
  <article
    class="vk"
    :class="`vk--${variant}`"
    :style="{ '--vk-accent': accent }"
    role="button"
    tabindex="0"
    @click="$emit('edit')"
    @keydown.enter.prevent="$emit('edit')"
  >
    <div class="vk__preview">
      <!-- Schnellblock: Mini-Abbild der echten Box -->
      <div v-if="variant === 'schnellblock'" class="vk-mini" aria-hidden="true">
        <span class="vk-mini__bar" />
        <div class="vk-mini__rows">
          <span v-for="(w, i) in blockRows" :key="i" class="vk-mini__row">
            <span class="vk-mini__pill" :style="{ width: w.pill }" />
            <span class="vk-mini__line" :style="{ width: w.line }" />
          </span>
        </div>
      </div>
      <!-- Startnotiz: Notiz-Seite -->
      <div v-else class="vk-page" aria-hidden="true">
        <span class="vk-page__head" />
        <span v-for="(w, i) in pageLines" :key="i" class="vk-page__line" :style="{ width: w }" />
      </div>

      <span v-if="variant === 'schnellblock'" class="vk__slash" title="Per / einfügbar" aria-hidden="true">/</span>

      <div class="vk__actions">
        <button
          v-if="variant === 'startnotiz'"
          type="button"
          class="vk__act vk__act--go"
          title="Notiz starten"
          aria-label="Notiz starten"
          @click.stop="$emit('primary')"
        ><v-icon size="16">mdi-note-plus-outline</v-icon></button>
        <button type="button" class="vk__act" title="Bearbeiten" aria-label="Bearbeiten" @click.stop="$emit('edit')">
          <v-icon size="15">mdi-pencil-outline</v-icon>
        </button>
        <button type="button" class="vk__act vk__act--danger" title="Löschen" aria-label="Löschen" @click.stop="$emit('delete')">
          <v-icon size="15">mdi-trash-can-outline</v-icon>
        </button>
      </div>
    </div>

    <div class="vk__meta">
      <span class="vk__chip" aria-hidden="true">
        <v-icon size="16">{{ variant === 'startnotiz' ? 'mdi-note-outline' : 'mdi-shape-outline' }}</v-icon>
      </span>
      <span class="vk__title">{{ title || 'Ohne Titel' }}</span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  variant: { type: String, default: 'schnellblock' }, // 'schnellblock' | 'startnotiz'
  title: { type: String, default: '' },
  accent: { type: String, default: 'var(--pm-accent, #006b75)' },
  fields: { type: Array, default: () => [] },
});

defineEmits(['edit', 'delete', 'primary']);

// Ruhige, leicht variierende Balkenbreiten – rein dekorativ, abgeleitet aus der
// Feldzahl, damit die Vorschau zum Block „passt".
const BLOCK_PATTERN = [
  { pill: '30%', line: '54%' },
  { pill: '24%', line: '68%' },
  { pill: '34%', line: '48%' },
];
const blockRows = computed(() => {
  const count = Math.min(3, Math.max(2, (props.fields || []).length || 2));
  return BLOCK_PATTERN.slice(0, count);
});
const pageLines = ['88%', '96%', '70%'];
</script>

<style scoped>
.vk {
  --vk-accent: var(--pm-accent, #006b75);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  cursor: pointer;
  transition: transform 130ms cubic-bezier(0.2, 0, 0, 1), box-shadow 130ms ease, border-color 130ms ease;
}
.vk:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--vk-accent) 40%, var(--pm-divider, #d8dfe1));
  box-shadow: 0 8px 22px color-mix(in srgb, var(--vk-accent) 22%, transparent);
}
.vk:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--vk-accent) 55%, transparent);
}

/* ── Vorschau ─────────────────────────────────────────────────────────────── */
.vk__preview {
  position: relative;
  height: 108px;
  padding: 14px;
  display: flex;
}
.vk--schnellblock .vk__preview { background: color-mix(in srgb, var(--vk-accent) 9%, var(--pm-content-surface, #fff)); }
.vk--startnotiz .vk__preview { background: color-mix(in srgb, var(--pm-text, #0e181b) 4%, var(--pm-content-surface, #fff)); }

/* Mini-Box (Schnellblock) */
.vk-mini {
  flex: 1;
  display: flex;
  border-radius: 8px;
  overflow: hidden;
  background: var(--pm-content-surface, #fff);
  border: 1px solid color-mix(in srgb, var(--vk-accent) 26%, var(--pm-divider, #d8dfe1));
}
.vk-mini__bar { width: 4px; flex: none; background: var(--vk-accent); }
.vk-mini__rows { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 9px; padding: 0 12px; }
.vk-mini__row { display: flex; align-items: center; gap: 8px; }
.vk-mini__pill { height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--vk-accent) 42%, var(--pm-divider, #d8dfe1)); flex: none; }
.vk-mini__line { height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--vk-accent) 16%, var(--pm-divider, #d8dfe1)); flex: 1; }

/* Mini-Seite (Startnotiz) */
.vk-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: 8px;
  padding: 13px 14px;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
}
.vk-page__head { height: 8px; width: 46%; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 26%, transparent); margin-bottom: 2px; }
.vk-page__line { height: 6px; border-radius: 3px; background: color-mix(in srgb, var(--pm-text, #0e181b) 12%, transparent); }
.vk-page__line:last-child { opacity: 0.6; }

/* „/"-Badge (Einfüge-Hinweis, Schnellblock) */
.vk__slash {
  position: absolute;
  top: 10px;
  right: 10px;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.78rem;
  font-weight: 600;
  color: color-mix(in srgb, var(--vk-accent) 72%, var(--pm-text, #0e181b));
  background: color-mix(in srgb, var(--vk-accent) 15%, var(--pm-content-surface, #fff));
  transition: opacity 120ms ease;
}
.vk:hover .vk__slash { opacity: 0; }

/* Hover-Aktionen (Icon-Buttons) */
.vk__actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 3px;
  padding: 3px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 80%, transparent);
  backdrop-filter: blur(3px);
  opacity: 0;
  transform: translateY(-2px);
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease;
}
.vk:hover .vk__actions,
.vk:focus-within .vk__actions { opacity: 1; transform: none; pointer-events: auto; }
.vk__act {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  transition: color 120ms ease, background 120ms ease;
}
.vk__act:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); color: var(--pm-text, #0e181b); }
.vk__act--danger:hover { color: var(--pm-danger, #c0392b); background: color-mix(in srgb, var(--pm-danger, #c0392b) 12%, transparent); }
.vk__act--go {
  color: var(--pm-accent, #006b75);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 14%, transparent);
}
.vk__act--go:hover { color: var(--pm-accent-contrast, #fff); background: var(--pm-accent, #006b75); }

/* ── Meta (Icon-Chip + Titel) ─────────────────────────────────────────────── */
.vk__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px;
  border-top: 1px solid var(--pm-divider, #d8dfe1);
}
.vk__chip {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: none;
  border-radius: 8px;
  color: var(--vk-accent);
  background: color-mix(in srgb, var(--vk-accent) 14%, transparent);
}
.vk--startnotiz .vk__chip { color: var(--pm-muted, #535e62); background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); }
.vk__title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--pm-text, #0e181b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (prefers-reduced-motion: reduce) {
  .vk, .vk__actions, .vk__slash { transition: none; }
  .vk:hover { transform: none; }
}
</style>
