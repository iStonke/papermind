<template>
    <Teleport to="body">
      <div
        v-if="shortcutsOpen"
        class="pm-shortcuts-overlay"
        @click.self="closeShortcuts"
        @keydown.esc.prevent="closeShortcuts"
      >
          <div
            class="pm-shortcuts"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pm-shortcuts-title"
          >
            <div class="pm-shortcuts__head">
              <h2 id="pm-shortcuts-title" class="pm-shortcuts__title">Tastenkürzel</h2>
              <button
                ref="shortcutsCloseEl"
                type="button"
                class="pm-shortcuts__close"
                aria-label="Schließen"
                @click="closeShortcuts"
              >
                <v-icon size="18">mdi-close</v-icon>
              </button>
            </div>
            <div class="pm-shortcuts__grid">
              <section v-for="group in shortcutGroups" :key="group.title" class="pm-shortcuts__group">
                <h3 class="pm-shortcuts__group-title">{{ group.title }}</h3>
                <ul class="pm-shortcuts__list">
                  <li v-for="row in group.items" :key="row.label" class="pm-shortcuts__row">
                    <span class="pm-shortcuts__label">{{ row.label }}</span>
                    <span class="pm-shortcuts__keys">
                      <kbd v-for="(key, i) in row.keys" :key="i">{{ key }}</kbd>
                    </span>
                  </li>
                </ul>
              </section>
            </div>
          </div>
      </div>
    </Teleport>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue';
const emit = defineEmits(['close']);
const shortcutsOpen = ref(false);
const isMacKeyboard = typeof navigator !== 'undefined'
  && /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent || '');
const modKeyLabel = isMacKeyboard ? '⌘' : 'Strg';
const altKeyLabel = isMacKeyboard ? '⌥' : 'Alt';
const shiftKeyLabel = isMacKeyboard ? '⇧' : 'Umschalt';
const shortcutGroups = computed(() => [
  {
    title: 'Text',
    items: [
      { label: 'Fett', keys: [modKeyLabel, 'B'] },
      { label: 'Kursiv', keys: [modKeyLabel, 'I'] },
      { label: 'Durchgestrichen', keys: [modKeyLabel, shiftKeyLabel, 'S'] },
      { label: 'Markieren', keys: [modKeyLabel, shiftKeyLabel, 'H'] },
      { label: 'Inline-Code', keys: [modKeyLabel, 'E'] },
    ],
  },
  {
    title: 'Absätze',
    items: [
      { label: 'Überschrift 2/3/4', keys: [modKeyLabel, altKeyLabel, '2 / 3 / 4'] },
      { label: 'Fließtext', keys: [modKeyLabel, altKeyLabel, '0'] },
      { label: 'Zitat', keys: [modKeyLabel, shiftKeyLabel, 'B'] },
      { label: 'Codeblock', keys: [modKeyLabel, altKeyLabel, 'C'] },
    ],
  },
  {
    title: 'Listen',
    items: [
      { label: 'Aufzählung', keys: [modKeyLabel, shiftKeyLabel, '8'] },
      { label: 'Nummerierte Liste', keys: [modKeyLabel, shiftKeyLabel, '7'] },
    ],
  },
  {
    // Zeilenanfang-Kürzel (InputRules aus callout.js): Zeichen + Leertaste.
    title: 'Hinweisblöcke',
    items: [
      { label: 'Wichtig', keys: ['!', '␣'] },
      { label: 'Frage', keys: ['?', '␣'] },
      { label: 'Entscheidung', keys: ['=', '␣'] },
    ],
  },
  {
    title: 'Einfügen & Aktionen',
    items: [
      { label: 'Hyperlink', keys: [modKeyLabel, 'K'] },
      { label: 'Befehlsmenü', keys: ['/'] },
      { label: 'Suchen & Ersetzen', keys: [modKeyLabel, 'F'] },
      { label: 'Rückgängig', keys: [modKeyLabel, 'Z'] },
      { label: 'Wiederherstellen', keys: [modKeyLabel, shiftKeyLabel, 'Z'] },
      { label: 'Diese Übersicht', keys: [modKeyLabel, '/'] },
    ],
  },
]);
function openShortcuts() {
  shortcutsOpen.value = true;
  nextTick(() => shortcutsCloseEl.value?.focus?.());
}
function closeShortcuts() {
  shortcutsOpen.value = false;
  emit('close');
}
const shortcutsCloseEl = ref(null);

defineExpose({ open: openShortcuts, close: closeShortcuts });
</script>

<style scoped>
/* ── Tastenkürzel-Übersicht ─────────────────────────────────────────────────── */
.pm-shortcuts-overlay {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 34%, transparent);
  backdrop-filter: blur(2px);
}
.pm-shortcuts {
  width: min(900px, 100%);
  max-height: min(80vh, 640px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 14px;
  box-shadow: 0 24px 60px color-mix(in srgb, var(--pm-text, #0e181b) 30%, transparent);
}
.pm-shortcuts__head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 13px;
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
}
.pm-shortcuts__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 680;
  color: var(--pm-text, #0e181b);
}
.pm-shortcuts__close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.pm-shortcuts__close:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); color: var(--pm-text, #0e181b); }
.pm-shortcuts__close:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }
.pm-shortcuts__grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 22px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px 32px;
  align-content: start;
}
.pm-shortcuts__group-title {
  margin: 4px 0 6px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pm-muted, #535e62);
}
.pm-shortcuts__list { list-style: none; margin: 0; padding: 0; }
.pm-shortcuts__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 5px 0;
}
.pm-shortcuts__label { font-size: 0.9rem; color: var(--pm-text, #0e181b); }
.pm-shortcuts__keys { display: inline-flex; gap: 4px; flex: none; }
.pm-shortcuts__keys kbd {
  min-width: 22px;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-bottom-width: 2px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 4%, var(--pm-content-surface, #fff));
  font: 500 0.78rem/1.4 'IBM Plex Mono', ui-monospace, monospace;
  color: var(--pm-text, #0e181b);
  text-align: center;
}
@media (max-width: 560px) {
  .pm-shortcuts__grid { grid-template-columns: 1fr; }
}
/* Eintritts-Animation per CSS-Keyframes (nicht Vue-Transition-verwaltet), damit
   das teleportierte Overlay nicht in einem Leave-Zustand hängen bleiben kann. */
.pm-shortcuts-overlay { animation: pm-shortcuts-fade 140ms ease both; }
.pm-shortcuts-overlay .pm-shortcuts { animation: pm-shortcuts-pop 170ms cubic-bezier(0.16, 1, 0.3, 1) both; }
@keyframes pm-shortcuts-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes pm-shortcuts-pop {
  from { transform: translateY(8px) scale(0.98); opacity: 0; }
  to { transform: none; opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .pm-shortcuts-overlay,
  .pm-shortcuts-overlay .pm-shortcuts { animation: none; }
}
</style>
