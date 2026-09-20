<template>
  <!-- Verhalten wie jeder PaperMind-Dialog (BaseDialog: Scrim, Fokus-Handling,
       Scroll-Lock, Standard-Transition/Schließen). Nur die Fläche hebt sich
       optisch ab: milchig, leicht durchscheinend, hell/dunkel je nach Modus. -->
  <BaseDialog
    :model-value="modelValue"
    title="Tastenkürzel"
    header-subtitle="Alle Tastaturkürzel und Mausgesten in PaperMind."
    icon="mdi-keyboard-outline"
    variant="info"
    :show-footer="false"
    scrollable
    :max-width="1040"
    :content-class="dialogContentClass"
    card-class="pm-keys-card"
    body-class="pm-keys-scope"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="pm-keys">
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

      <!-- Inhalt: beide Panels liegen übereinander (Kreuzblende); nur das aktive
           bestimmt die Höhe. Der Container animiert die gemessene Höhe des
           aktiven Panels → dynamische Fensterhöhe ohne Leerraum und ohne
           Kollabieren/Ruckeln. -->
      <div ref="bodyRef" class="pm-keys__body" :style="bodyStyle">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="pm-keys__panel"
          :class="{ 'is-active': tab.id === activeTab }"
          role="tabpanel"
          :aria-hidden="tab.id !== activeTab"
        >
          <div class="pm-keys__grid">
            <section
              v-for="group in tab.groups"
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
        </div>
      </div>
    </div>
  </BaseDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import { SHORTCUT_ACTIONS, SHORTCUTS } from '../keyboard/shortcuts';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue']);

// Dynamische Fensterhöhe: der Container übernimmt die gemessene Höhe des aktiven
// Panels und animiert Änderungen weich (CSS-transition auf height). So bleibt
// unter dem kürzeren Tab kein Leerraum, und der Wechsel ruckelt nicht.
const bodyRef = ref(null);
const bodyHeight = ref(null);
const bodyStyle = computed(() => (
  bodyHeight.value != null ? { height: `${bodyHeight.value}px` } : null
));
function syncHeight() {
  const body = bodyRef.value;
  if (!body) return;
  const active = body.querySelector('.pm-keys__panel.is-active');
  if (active) bodyHeight.value = active.offsetHeight;
}

const theme = useTheme();
const isDark = computed(() => Boolean(theme.global?.current?.value?.dark));
// Bei aktiviertem Glass/Aurora-Look darf die Milchglasfläche etwas transparenter
// sein; ohne opt-in bleibt sie kräftiger, damit der Text überall lesbar ist.
const glassEnabled = computed(() => {
  if (typeof document === 'undefined') return false;
  return document.documentElement.hasAttribute('data-glass')
    || document.body?.hasAttribute?.('data-glass');
});

// Klasse am (teleportierten) v-dialog-Content, damit die globalen Milchglas-
// Regeln greifen und Hell/Dunkel unterscheiden können.
const dialogContentClass = computed(() => [
  'pm-keys-dialog',
  isDark.value ? 'pm-keys-dialog--dark' : 'pm-keys-dialog--light',
  { 'pm-keys-dialog--glass': glassEnabled.value },
]);

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

// Höhe nach jedem Tab-Wechsel und beim Öffnen neu messen (nach dem Render, damit
// das aktive Panel bereits im Fluss liegt). Fensterbreiten-Änderung kann das
// Spaltenraster umbrechen → ebenfalls neu messen.
watch(activeTab, () => nextTick(syncHeight));
watch(
  () => props.modelValue,
  (open) => { if (open) nextTick(syncHeight); },
);
onMounted(() => {
  if (typeof window !== 'undefined') window.addEventListener('resize', syncHeight);
});
onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('resize', syncHeight);
});
</script>

<!-- Milchglas-Optik: überschreibt die undurchsichtige Standardfläche des
     BaseDialog. Global (unscoped), weil Karte/Content teleportiert werden. -->
<style>
/* Öffnen: die (frostige) Karte erscheint SOFORT mit vollem backdrop-filter –
   nur der Scrim dahinter fadet ein. So gibt es keinen Zwischenframe, in dem der
   Hintergrund durchschlägt. (Ein Opacity-Fade des Contents würde die ohnehin
   transluzente Fläche kurz doppelt durchsichtig machen und den Hintergrund
   zeigen; ein scale-Transform würde den backdrop-filter deaktivieren.) */
.pm-keys-dialog.pm-dialog-enter-active {
  transition: none;
}
.pm-keys-dialog.pm-dialog-enter-from {
  opacity: 1;
  transform: none;
}
/* Schließen: kurzes, sauberes Ausblenden ohne Transform. */
.pm-keys-dialog.pm-dialog-leave-active {
  transition: opacity 160ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}
.pm-keys-dialog.pm-dialog-leave-to {
  opacity: 0;
  transform: none;
}

/* Der teleportierte Overlay-Wrapper trägt eine eigene (halbtransparente) Fläche
   für den Milchglas-Rahmen. Ohne eigenen Radius bleiben seine Ecken eckig und
   lugen hinter der runden Karte hervor – deshalb denselben Fensterradius wie
   die Karte (var(--pm-window-radius)) setzen, damit die Ecken sauber sind. */
.pm-keys-dialog.v-overlay__content {
  border-radius: var(--pm-window-radius, 24px);
}

.pm-keys-dialog .pm-keys-card.pm-dialog {
  /* Milchig & deutlich durchscheinend – die Blur-Schicht hält den Text lesbar. */
  background: rgba(255, 255, 255, 0.62);
  border-color: rgba(255, 255, 255, 0.5);
  -webkit-backdrop-filter: blur(26px) saturate(150%);
  backdrop-filter: blur(26px) saturate(150%);
  box-shadow:
    0 32px 80px rgba(15, 23, 42, 0.30),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
  /* Beim Öffnen startet die Fläche fast deckend und wird in die transluzente
     Milchglasfläche überblendet. Das überbrückt die ein, zwei Frames, die der
     Browser braucht, um den backdrop-filter zu rastern – in denen die Karte
     sonst transluzent, aber noch unscharf ist und der Hintergrund durchblitzt.
     `backwards` erzwingt den deckenden Startwert schon im allerersten Frame. */
  animation: pm-keys-frost-in 320ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)) backwards;
}
.pm-keys-dialog--dark .pm-keys-card.pm-dialog {
  background: rgba(24, 32, 42, 0.55);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow:
    0 32px 80px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  animation-name: pm-keys-frost-in-dark;
}
@keyframes pm-keys-frost-in {
  from { background-color: rgba(255, 255, 255, 0.97); }
}
@keyframes pm-keys-frost-in-dark {
  from { background-color: rgba(24, 32, 42, 0.96); }
}
/* Bei aktivem Glass-Look darf die Fläche etwas transparenter wirken. */
.pm-keys-dialog--glass .pm-keys-card.pm-dialog { background: rgba(255, 255, 255, 0.5); }
.pm-keys-dialog--glass.pm-keys-dialog--dark .pm-keys-card.pm-dialog { background: rgba(24, 32, 42, 0.45); }

/* Fallback ohne backdrop-filter-Unterstützung: kräftigere Fläche. */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .pm-keys-dialog .pm-keys-card.pm-dialog { background: rgba(248, 250, 251, 0.97); }
  .pm-keys-dialog--dark .pm-keys-card.pm-dialog { background: rgba(24, 32, 42, 0.97); }
}
</style>

<style scoped>
/* ── Innenleben: Tabs + Querformat-Raster ─────────────────────────────────── */
.pm-keys { color: rgb(var(--v-theme-on-surface)); }

/* Tabs ------------------------------------------------------------------- */
.pm-keys__tabs {
  display: flex;
  gap: 6px;
  margin: -4px 0 16px;
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
:global(.pm-keys-dialog--dark) .pm-keys__tab.is-active {
  background: color-mix(in srgb, #56d6c9 20%, transparent);
  border-color: color-mix(in srgb, #56d6c9 40%, transparent);
  color: #7fe6db;
}
.pm-keys__tab:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }

/* Panels überlagern sich (Kreuzblende). Nur das aktive Panel liegt im Fluss und
   bestimmt damit die Höhe; der Container animiert die per JS gesetzte Höhe →
   dynamische Fensterhöhe ohne Leerraum, ohne Kollabieren. */
.pm-keys__body {
  position: relative;
  overflow: hidden;
  transition: height 300ms cubic-bezier(0.16, 1, 0.3, 1);
}
.pm-keys__panel {
  position: absolute;
  inset: 0 0 auto 0;
  min-width: 0;
  opacity: 0;
  visibility: hidden;
  transform: translateY(6px);
  pointer-events: none;
  transition:
    opacity 200ms ease,
    transform 260ms cubic-bezier(0.16, 1, 0.3, 1),
    visibility 0s linear 200ms;
}
.pm-keys__panel.is-active {
  position: relative;
  opacity: 1;
  visibility: visible;
  transform: none;
  pointer-events: auto;
  transition:
    opacity 220ms ease,
    transform 260ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* Inhalt: Querformat-Spaltenraster -------------------------------------- */
.pm-keys__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  /* Gleicher Abstand vertikal wie horizontal zwischen den Kacheln. */
  gap: 16px;
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
:global(.pm-keys-dialog--dark) .pm-keys__key {
  background: color-mix(in srgb, #ffffff 8%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  .pm-keys__body { transition: none; }
  .pm-keys__panel { transition: opacity 1ms linear, visibility 0s linear 1ms; transform: none; }
  .pm-keys__panel.is-active { transition: opacity 1ms linear; transform: none; }
}

@media (max-width: 620px) {
  .pm-keys__grid { grid-template-columns: 1fr; }
}
</style>
