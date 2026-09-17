<template>
  <Teleport to="body">
    <Transition name="pm-keys-fade">
      <div
        v-if="modelValue"
        class="pm-keys-overlay"
        :class="[themeClass, { 'pm-keys-overlay--glass': glassEnabled }]"
        role="presentation"
        @click.self="close"
        @keydown.esc.prevent.stop="close"
      >
        <div
          ref="panelRef"
          class="pm-keys"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pm-keys-title"
          tabindex="-1"
        >
          <!-- Kopf: Titel + Tabs + Schließen ------------------------------- -->
          <header class="pm-keys__head">
            <div class="pm-keys__head-main">
              <span class="pm-keys__head-icon" aria-hidden="true">
                <v-icon size="20">mdi-keyboard-outline</v-icon>
              </span>
              <div class="pm-keys__head-text">
                <h2 id="pm-keys-title" class="pm-keys__title">Tastenkürzel</h2>
                <p class="pm-keys__subtitle">Alle Tastaturkürzel und Mausgesten in PaperMind.</p>
              </div>
            </div>
            <button
              ref="closeEl"
              type="button"
              class="pm-keys__close"
              aria-label="Schließen"
              @click="close"
            >
              <v-icon size="18">mdi-close</v-icon>
            </button>
          </header>

          <nav class="pm-keys__tabs" role="tablist" aria-label="Kategorien">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              type="button"
              class="pm-keys__tab"
              :class="{ 'is-active': tab.id === activeTab }"
              role="tab"
              :aria-selected="tab.id === activeTab ? 'true' : 'false'"
              @click="activeTab = tab.id"
            >
              <v-icon size="16" class="pm-keys__tab-icon">{{ tab.icon }}</v-icon>
              <span>{{ tab.label }}</span>
            </button>
          </nav>

          <!-- Inhalt: Querformat-Spaltenraster, animierter Tab-Wechsel ----- -->
          <div class="pm-keys__body">
            <Transition name="pm-keys-tab" mode="out-in">
              <div
                :key="activeTab"
                class="pm-keys__grid"
                role="tabpanel"
              >
                <section
                  v-for="group in activeGroups"
                  :key="group.title"
                  class="pm-keys__group"
                >
                  <h3 class="pm-keys__group-title">{{ group.title }}</h3>
                  <ul class="pm-keys__list">
                    <li
                      v-for="item in group.items"
                      :key="item.label"
                      class="pm-keys__row"
                    >
                      <span class="pm-keys__label">{{ item.label }}</span>
                      <span class="pm-keys__combos">
                        <template
                          v-for="(combo, ci) in item.combos"
                          :key="ci"
                        >
                          <span v-if="ci > 0" class="pm-keys__or">/</span>
                          <span class="pm-keys__combo">
                            <kbd
                              v-for="(key, ki) in combo"
                              :key="ki"
                              class="pm-keys__key"
                            >{{ key }}</kbd>
                          </span>
                        </template>
                      </span>
                    </li>
                  </ul>
                </section>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import { SHORTCUT_ACTIONS, SHORTCUTS } from '../keyboard/shortcuts';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue']);

const theme = useTheme();
const isDark = computed(() => Boolean(theme.global?.current?.value?.dark));
const themeClass = computed(() => (isDark.value ? 'pm-keys--dark' : 'pm-keys--light'));
// Bei aktiviertem Glass/Aurora-Look darf die Milchglasfläche etwas transparenter
// sein; ohne opt-in bleibt sie kräftiger, damit der Text überall lesbar ist.
const glassEnabled = computed(() => {
  if (typeof document === 'undefined') return false;
  return document.documentElement.hasAttribute('data-glass')
    || document.body?.hasAttribute?.('data-glass');
});

const panelRef = ref(null);
const closeEl = ref(null);
const activeTab = ref('general');

const isMacKeyboard = typeof navigator !== 'undefined'
  && /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent || '');
const modKey = isMacKeyboard ? '⌘' : 'Strg';
const altKey = isMacKeyboard ? '⌥' : 'Alt';
const shiftKey = isMacKeyboard ? '⇧' : 'Umschalt';

const KEY_LABELS = {
  Enter: '↵',
  ' ': 'Leer',
  Escape: 'Esc',
  Backspace: '⌫',
  ArrowLeft: '←',
  ArrowRight: '→',
  ArrowUp: '↑',
  ArrowDown: '↓',
};

function formatKey(key) {
  return KEY_LABELS[key] ?? key;
}

// Wandelt die zentral definierten Aktions-Tasten (shortcuts.js) in Combos um –
// jede Taste zählt dabei als eigenständige Alternative.
function combosFor(action) {
  return (SHORTCUTS[action]?.keys ?? []).map((key) => [formatKey(key)]);
}

const tabs = computed(() => [
  {
    id: 'general',
    label: 'Allgemein',
    icon: 'mdi-application-outline',
    groups: [
      {
        title: 'Allgemein',
        items: [
          { label: 'Befehlsmenü öffnen / schließen', combos: [[modKey, 'K']] },
          { label: 'Tastenkürzel anzeigen', combos: [['?'], [modKey, '/']] },
          { label: 'Dialog / Auswahl schließen', combos: combosFor(SHORTCUT_ACTIONS.CANCEL) },
        ],
      },
      {
        title: 'Suche',
        items: [
          { label: 'Suche bestätigen', combos: combosFor(SHORTCUT_ACTIONS.SEARCH_SUBMIT) },
          { label: 'Suche abbrechen', combos: combosFor(SHORTCUT_ACTIONS.SEARCH_CANCEL) },
        ],
      },
      {
        title: 'Navigation',
        items: [
          { label: 'Vorheriges Element', combos: combosFor(SHORTCUT_ACTIONS.MOVE_PREVIOUS) },
          { label: 'Nächstes Element', combos: combosFor(SHORTCUT_ACTIONS.MOVE_NEXT) },
          { label: 'Schritt zurück', combos: combosFor(SHORTCUT_ACTIONS.STEP_PREVIOUS) },
          { label: 'Schritt vor', combos: combosFor(SHORTCUT_ACTIONS.STEP_NEXT) },
        ],
      },
      {
        title: 'Aktionen',
        items: [
          { label: 'Dokument in den Papierkorb', combos: combosFor(SHORTCUT_ACTIONS.TRASH) },
          { label: 'Element aktivieren / auswählen', combos: combosFor(SHORTCUT_ACTIONS.ACTIVATE) },
          { label: 'Primäre Aktion bestätigen', combos: combosFor(SHORTCUT_ACTIONS.PRIMARY) },
        ],
      },
      {
        title: 'Mausgesten',
        items: [
          { label: 'Auswahlmodus + Dokument selektieren', combos: [[`${modKey} + Klick`]] },
        ],
      },
    ],
  },
  {
    id: 'notes',
    label: 'Notizen',
    icon: 'mdi-note-edit-outline',
    groups: [
      {
        title: 'Text',
        items: [
          { label: 'Fett', combos: [[modKey, 'B']] },
          { label: 'Kursiv', combos: [[modKey, 'I']] },
          { label: 'Durchgestrichen', combos: [[modKey, shiftKey, 'S']] },
          { label: 'Markieren', combos: [[modKey, shiftKey, 'H']] },
          { label: 'Inline-Code', combos: [[modKey, 'E']] },
        ],
      },
      {
        title: 'Absätze',
        items: [
          { label: 'Überschrift 2 / 3 / 4', combos: [[modKey, altKey, '2 / 3 / 4']] },
          { label: 'Fließtext', combos: [[modKey, altKey, '0']] },
          { label: 'Zitat', combos: [[modKey, shiftKey, 'B']] },
          { label: 'Codeblock', combos: [[modKey, altKey, 'C']] },
        ],
      },
      {
        title: 'Listen',
        items: [
          { label: 'Aufzählung', combos: [[modKey, shiftKey, '8']] },
          { label: 'Nummerierte Liste', combos: [[modKey, shiftKey, '7']] },
        ],
      },
      {
        // Zeilenanfang-Kürzel (InputRules aus callout.js): Zeichen + Leertaste.
        title: 'Hinweisblöcke',
        items: [
          { label: 'Wichtig', combos: [['!', '␣']] },
          { label: 'Frage', combos: [['?', '␣']] },
          { label: 'Entscheidung', combos: [['=', '␣']] },
        ],
      },
      {
        title: 'Einfügen & Aktionen',
        items: [
          { label: 'Hyperlink', combos: [[modKey, 'K']] },
          { label: 'Befehlsmenü', combos: [['/']] },
          { label: 'Suchen & Ersetzen', combos: [[modKey, 'F']] },
          { label: 'Rückgängig', combos: [[modKey, 'Z']] },
          { label: 'Wiederherstellen', combos: [[modKey, shiftKey, 'Z']] },
          { label: 'Diese Übersicht', combos: [[modKey, '/']] },
        ],
      },
    ],
  },
]);

const activeGroups = computed(
  () => tabs.value.find((tab) => tab.id === activeTab.value)?.groups ?? [],
);

function close() {
  emit('update:modelValue', false);
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      nextTick(() => {
        (panelRef.value ?? closeEl.value)?.focus?.();
      });
    }
  },
);
</script>

<style scoped>
/* ── Milchglas-Übersicht: hebt sich bewusst vom Standarddialog ab ─────────── */
.pm-keys-overlay {
  position: fixed;
  inset: 0;
  z-index: 2500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.34);
  -webkit-backdrop-filter: blur(3px);
  backdrop-filter: blur(3px);
}
.pm-keys--dark.pm-keys-overlay {
  background: rgba(2, 6, 12, 0.52);
}

.pm-keys {
  /* Querformat: breit statt hoch. */
  width: min(1040px, 100%);
  max-height: min(86vh, 660px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 22px;
  outline: none;
  /* Milchig, nur dezent durchschimmernd – heller/dunkler je nach Modus. */
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.6);
  -webkit-backdrop-filter: blur(26px) saturate(150%);
  backdrop-filter: blur(26px) saturate(150%);
  box-shadow:
    0 32px 80px rgba(15, 23, 42, 0.30),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
  color: #10201f;
}
.pm-keys--dark .pm-keys {
  background: rgba(24, 32, 42, 0.85);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow:
    0 32px 80px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  color: #e8eef1;
}
/* Bei aktivem Glass-Look darf die Fläche etwas transparenter wirken. */
.pm-keys-overlay--glass .pm-keys { background: rgba(255, 255, 255, 0.8); }
.pm-keys-overlay--glass.pm-keys--dark .pm-keys { background: rgba(24, 32, 42, 0.74); }

/* Fallback ohne backdrop-filter-Unterstützung: kräftigere Fläche. */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .pm-keys { background: rgba(248, 250, 251, 0.97); }
  .pm-keys--dark .pm-keys { background: rgba(24, 32, 42, 0.97); }
}

/* Kopf ------------------------------------------------------------------- */
.pm-keys__head {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 14px;
}
.pm-keys__head-main { display: flex; align-items: flex-start; gap: 13px; min-width: 0; }
.pm-keys__head-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: 11px;
  background: color-mix(in srgb, currentColor 10%, transparent);
  color: var(--pm-accent, #006b75);
}
.pm-keys--dark .pm-keys__head-icon { color: #56d6c9; }
.pm-keys__head-text { min-width: 0; }
.pm-keys__title { margin: 0; font-size: 1.18rem; font-weight: 700; line-height: 1.2; }
.pm-keys__subtitle {
  margin: 2px 0 0;
  font-size: 0.86rem;
  line-height: 1.35;
  opacity: 0.62;
}
.pm-keys__close {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: currentColor;
  opacity: 0.7;
  cursor: pointer;
  transition: background-color 120ms ease, opacity 120ms ease;
}
.pm-keys__close:hover { background: color-mix(in srgb, currentColor 12%, transparent); opacity: 1; }
.pm-keys__close:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }

/* Tabs ------------------------------------------------------------------- */
.pm-keys__tabs {
  flex: none;
  display: flex;
  gap: 6px;
  padding: 0 24px 14px;
}
.pm-keys__tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 15px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: color-mix(in srgb, currentColor 6%, transparent);
  color: currentColor;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  opacity: 0.72;
  transition: background-color 130ms ease, opacity 130ms ease, border-color 130ms ease;
}
.pm-keys__tab:hover { opacity: 0.95; }
.pm-keys__tab-icon { opacity: 0.85; }
.pm-keys__tab.is-active {
  opacity: 1;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 16%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  color: var(--pm-accent, #006b75);
}
.pm-keys--dark .pm-keys__tab.is-active {
  background: color-mix(in srgb, #56d6c9 20%, transparent);
  border-color: color-mix(in srgb, #56d6c9 40%, transparent);
  color: #7fe6db;
}
.pm-keys__tab:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }

/* Inhalt: Querformat-Spaltenraster -------------------------------------- */
.pm-keys__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 24px 22px;
}
.pm-keys__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 8px 22px;
  align-content: start;
}
.pm-keys__group {
  break-inside: avoid;
  padding: 12px 14px 8px;
  border-radius: 14px;
  background: color-mix(in srgb, currentColor 4%, transparent);
  border: 1px solid color-mix(in srgb, currentColor 8%, transparent);
}
.pm-keys__group-title {
  margin: 0 0 6px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  opacity: 0.55;
}
.pm-keys__list { list-style: none; margin: 0; padding: 0; }
.pm-keys__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
  padding: 4px 0;
}
.pm-keys__label { font-size: 0.88rem; line-height: 1.3; }
.pm-keys__combos { display: inline-flex; align-items: center; gap: 6px; flex: none; }
.pm-keys__combo { display: inline-flex; gap: 4px; }
.pm-keys__or { font-size: 0.78rem; opacity: 0.4; }
.pm-keys__key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  padding: 2px 7px;
  border-radius: 7px;
  border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
  border-bottom-width: 2px;
  background: color-mix(in srgb, #ffffff 55%, transparent);
  font: 600 0.76rem/1.4 'IBM Plex Mono', ui-monospace, monospace;
  color: currentColor;
  text-align: center;
  white-space: nowrap;
}
.pm-keys--dark .pm-keys__key {
  background: color-mix(in srgb, #ffffff 8%, transparent);
}

/* Animation -------------------------------------------------------------- */
.pm-keys-fade-enter-active { transition: opacity 150ms ease; }
.pm-keys-fade-leave-active { transition: opacity 130ms ease; }
.pm-keys-fade-enter-from,
.pm-keys-fade-leave-to { opacity: 0; }
.pm-keys-fade-enter-active .pm-keys {
  animation: pm-keys-pop 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes pm-keys-pop {
  from { transform: translateY(10px) scale(0.985); opacity: 0; }
  to { transform: none; opacity: 1; }
}

/* Tab-Wechsel: sanftes Aus-/Einblenden mit leichtem Versatz (mode out-in). */
.pm-keys-tab-enter-active {
  transition: opacity 200ms ease, transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}
.pm-keys-tab-leave-active {
  transition: opacity 120ms ease, transform 120ms ease;
}
.pm-keys-tab-enter-from { opacity: 0; transform: translateY(8px); }
.pm-keys-tab-leave-to { opacity: 0; transform: translateY(-6px); }

@media (prefers-reduced-motion: reduce) {
  .pm-keys-fade-enter-active,
  .pm-keys-fade-leave-active,
  .pm-keys-fade-enter-active .pm-keys,
  .pm-keys-tab-enter-active,
  .pm-keys-tab-leave-active { transition: none; animation: none; }
}

@media (max-width: 620px) {
  .pm-keys__grid { grid-template-columns: 1fr; }
  .pm-keys__tabs { padding-bottom: 12px; }
}
</style>
