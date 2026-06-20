<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="820"
    card-class="pm-settings-card"
    body-class="pm-settings-body"
    footer-class="pm-settings-footer"
    title="Einstellungen"
    header-subtitle="Globale Voreinstellungen für dein PaperMind."
    description=""
    variant="info"
    primary-text="Fertig"
    :show-secondary="false"
    @primary="emit('update:modelValue', false)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="isSettingsLoading" class="settings-loading">
      <v-progress-circular indeterminate size="20" width="2" />
      <span>Einstellungen werden geladen...</span>
    </div>
    <template v-else>
      <div class="pm-settings-layout">
        <nav class="pm-settings-nav" role="tablist" aria-label="Einstellungskategorien">
          <button
            v-for="cat in settingsCategories"
            :key="`cat-${cat.value}`"
            type="button"
            class="pm-settings-nav__item"
            :class="{ 'pm-settings-nav__item--active': activeCategory === cat.value }"
            role="tab"
            :aria-selected="activeCategory === cat.value"
            @click="activeCategory = cat.value"
          >
            <v-icon size="18" class="pm-settings-nav__icon">{{ cat.icon }}</v-icon>
            <span>{{ cat.label }}</span>
          </button>
        </nav>

        <div class="pm-settings-panel">
        <section v-show="activeCategory === 'appearance'" class="pm-settings-section">
          <h3 class="pm-settings-title">Darstellung</h3>
          <div class="pm-settings-content">
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Farbvariation</div>
                <div class="pm-setting-description">Akzentfarbe der gesamten Oberfläche.</div>
              </div>
              <div
                class="settings-color-variant-picker"
                role="radiogroup"
                aria-label="Farbvariante auswählen"
              >
                <button
                  v-for="option in colorVariantOptions"
                  :key="`variant-${option.value}`"
                  type="button"
                  class="settings-color-variant-picker__item"
                  :class="{ 'settings-color-variant-picker__item--active': currentColorVariant === option.value }"
                  :style="{ '--variant-color': option.color }"
                  role="radio"
                  :aria-label="`Farbvariante: ${option.label}`"
                  :aria-checked="currentColorVariant === option.value"
                  :disabled="isSettingSaving.color_variant"
                  :title="option.label"
                  @click="onColorVariantChange(option.value)"
                  @pointerup.prevent="onColorVariantChange(option.value)"
                  @keydown.enter.prevent="onColorVariantChange(option.value)"
                  @keydown.space.prevent="onColorVariantChange(option.value)"
                >
                  <span class="settings-color-variant-picker__swatch" />
                </button>
              </div>
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Thema</div>
                <div class="pm-setting-description">Hell, dunkel oder entsprechend Systemeinstellung.</div>
              </div>
              <div
                class="settings-theme-segmented"
                role="radiogroup"
                aria-label="Thema auswählen"
                @keydown="handleThemeModeShortcut"
              >
                <button
                  v-for="option in themeModeOptions"
                  :key="`theme-${option.value}`"
                  type="button"
                  class="settings-theme-segmented__item"
                  :class="{ 'settings-theme-segmented__item--active': settingsDraft.ui.theme_mode === option.value }"
                  role="radio"
                  :aria-label="`Thema: ${option.label}`"
                  :aria-checked="settingsDraft.ui.theme_mode === option.value"
                  :disabled="isSettingSaving.theme_mode"
                  @click="onThemeModeChange(option.value)"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleShowFilenameSuffixFromRow"
              @keydown="handleSettingRowShortcut($event, toggleShowFilenameSuffixFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Dateiendung anzeigen</div>
                <div class="pm-setting-description">Blendet .pdf in Listen und Details ein/aus.</div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.showFilenameSuffix"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.show_filename_suffix"
                :disabled="isSettingSaving.show_filename_suffix"
                @click.stop
                @update:model-value="onShowFilenameSuffixChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAnimationsFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAnimationsFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Animationen</div>
                <div class="pm-setting-description">Sanfte Übergänge und Einblendeffekte in der Oberfläche.</div>
              </div>
              <v-switch
                :model-value="animationsEnabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                @click.stop
                @update:model-value="onAnimationsEnabledChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleDrawerRememberStateFromRow"
              @keydown="handleSettingRowShortcut($event, toggleDrawerRememberStateFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Dokumentdetails merken</div>
                <div class="pm-setting-description">
                  Merkt sich, ob die Schublade zuletzt ein- oder ausgeklappt war.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.drawerRememberState"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.drawer_remember_state"
                :disabled="isSettingSaving.drawer_remember_state"
                @click.stop
                @update:model-value="onDrawerRememberStateChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleDrawerAlwaysExpandedFromRow"
              @keydown="handleSettingRowShortcut($event, toggleDrawerAlwaysExpandedFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Dokumentdetails immer ausgeklappt</div>
                <div class="pm-setting-description">Die Schublade bleibt dauerhaft geöffnet.</div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.drawerAlwaysExpanded"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.drawer_always_expanded"
                :disabled="isSettingSaving.drawer_always_expanded"
                @click.stop
                @update:model-value="onDrawerAlwaysExpandedChange"
              />
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'documents'" class="pm-settings-section">
          <h3 class="pm-settings-title">Dokumente</h3>
          <div class="pm-settings-content">
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Sortierung</div>
                <div class="pm-setting-description">Legt die Standardreihenfolge in der Dokumentliste fest.</div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.sort_order"
                :items="sortOrderOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Sortierung"
                :loading="isSettingSaving.sort_order"
                :disabled="isSettingSaving.sort_order"
                @update:model-value="onSortOrderChange"
              />
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Zeitraum für „Zuletzt hinzugefügt"</div>
                <div class="pm-setting-description">
                  Legt fest, wie lange Dokumente nach dem Import in „Zuletzt hinzugefügt" erscheinen.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.recent_import_window_hours"
                :items="recentImportWindowOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Zeitraum"
                :loading="isSettingSaving.recent_import_window_hours"
                :disabled="isSettingSaving.recent_import_window_hours"
                @update:model-value="onRecentImportWindowChange"
              />
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Papierkorb automatisch leeren</div>
                <div class="pm-setting-description">
                  Legt fest, wann Dokumente im Papierkorb endgültig gelöscht werden.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.trash_retention_days"
                :items="trashRetentionOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Papierkorb"
                :loading="isSettingSaving.trash_retention_days"
                :disabled="isSettingSaving.trash_retention_days"
                @update:model-value="onTrashRetentionChange"
              />
            </div>

          </div>
        </section>

        <section v-show="activeCategory === 'ai'" class="pm-settings-section">
          <h3 class="pm-settings-title">KI &amp; Texterkennung</h3>
          <div class="pm-settings-content">

            <!-- KI-Analyse beim Import -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAutoTaggingFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoTaggingFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">KI-Analyse beim Import</div>
                <div class="pm-setting-description">Datum, Kategorie und Tags werden beim Hinzufügen automatisch erkannt und ausgefüllt.</div>
                <div v-if="settingsDraft.documents.auto_tagging" class="pm-setting-hint">
                  Kann je nach Modell/Hardware etwas dauern.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.auto_tagging"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.auto_tagging"
                :disabled="isSettingSaving.auto_tagging"
                @click.stop
                @update:model-value="onAutoTaggingChange"
              />
            </div>

            <!-- Ollama enable toggle -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleOllamaEnabledFromRow"
              @keydown="handleSettingRowShortcut($event, toggleOllamaEnabledFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Ollama (lokale KI) aktivieren</div>
                <div class="pm-setting-description">
                  Nutzt ein lokal laufendes Sprachmodell (z.&thinsp;B. llama3.2:3b) für präzisere
                  Dokument&shy;analyse beim Import. Daten verlassen das Gerät nicht.
                </div>
                <div v-if="settingsDraft.ollama.enabled" class="pm-setting-hint">
                  Ollama muss lokal laufen. Empfohlen: llama3.2:3b (Pi 5: ~20 s/Dokument).
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ollama.enabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.ollama_enabled"
                :disabled="isSettingSaving.ollama_enabled"
                @click.stop
                @update:model-value="onOllamaEnabledChange"
              />
            </div>

            <!-- Only shown when enabled -->
            <template v-if="settingsDraft.ollama.enabled">

              <!-- Base URL -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Basis-URL</div>
                  <div class="pm-setting-description">Adresse des Ollama-Servers (Standard: http://localhost:11434).</div>
                </div>
                <v-text-field
                  :model-value="settingsDraft.ollama.base_url"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  placeholder="http://localhost:11434"
                  :loading="isSettingSaving.ollama_base_url"
                  :disabled="isSettingSaving.ollama_base_url"
                  class="pm-setting-select"
                  @change="onOllamaBaseUrlChange($event.target.value)"
                />
              </div>

              <!-- Model -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Modell</div>
                  <div class="pm-setting-description">Ollama-Modell für die Import-Analyse.</div>
                </div>
                <v-combobox
                  :model-value="settingsDraft.ollama.model"
                  :items="ollamaModelPresets"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  :loading="isSettingSaving.ollama_model"
                  :disabled="isSettingSaving.ollama_model"
                  class="pm-setting-select"
                  @update:model-value="onOllamaModelChange"
                />
              </div>

              <!-- Max input chars -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Max. Textlänge (Zeichen)</div>
                  <div class="pm-setting-description">
                    Nur die ersten N Zeichen des OCR-Texts werden ans Modell übergeben.
                    Kürzere Texte = schneller, weniger Datenweitergabe bei externen Servern.
                  </div>
                </div>
                <v-select
                  :model-value="settingsDraft.ollama.max_input_chars"
                  :items="ollamaMaxCharsOptions"
                  item-title="label"
                  item-value="value"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  :loading="isSettingSaving.ollama_max_input_chars"
                  :disabled="isSettingSaving.ollama_max_input_chars"
                  class="pm-setting-select"
                  @update:model-value="onOllamaMaxInputCharsChange"
                />
              </div>

            </template>

            <!-- Automatisches OCR -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAutoOcrFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoOcrFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Automatisches OCR</div>
                <div class="pm-setting-description">Beim Import wird Text automatisch extrahiert.</div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.auto_ocr"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.auto_ocr"
                :disabled="isSettingSaving.auto_ocr"
                @click.stop
                @update:model-value="onAutoOcrChange"
              />
            </div>

            <!-- Erkennungssprache -->
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Erkennungssprache</div>
                <div class="pm-setting-description">
                  Standardsprache für die Texterkennung beim Importieren.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.ocr_doc_lang"
                :items="ocrDocLangOptions"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Erkennungssprache"
                :loading="isSettingSaving.ocr_doc_lang"
                :disabled="isSettingSaving.ocr_doc_lang"
                @update:model-value="onOcrDocLangChange"
              />
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'controls'" class="pm-settings-section">
          <h3 class="pm-settings-title">Bedienung</h3>
          <div class="pm-settings-content">
            <div class="pm-setting-row">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Tastaturkürzel</div>
                <div class="pm-setting-description">Zeigt verfügbare Tastenkürzel und Mausgesten.</div>
              </div>
              <v-btn
                class="pm-setting-action-btn"
                variant="tonal"
                color="primary"
                size="small"
                prepend-icon="mdi-keyboard-outline"
                @click="emit('open-shortcuts')"
              >
                Anzeigen
              </v-btn>
            </div>
          </div>
        </section>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import { getBaseUrl } from '../api/client';
import { useSettingsStore } from '../stores/settings';
import { notifyError } from '../stores/notifications';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';
import {
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildColorVariantPatch,
  buildDrawerAlwaysExpandedPatch,
  buildDrawerRememberStatePatch,
  buildOcrDocLangPatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildSortOrderPatch,
  buildThemeModePatch,
  buildTrashRetentionPatch
} from '../utils/settingsApi';

// ── Props / Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  modelValue: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue', 'reload-imports', 'open-shortcuts']);

// ── Stores / Theme ───────────────────────────────────────────────────────────

const theme = useTheme();
const settingsStore = useSettingsStore();
const settingsDraft = settingsStore.settingsDraft;
const isSettingSaving = settingsStore.isSettingSaving;
const isSettingsLoading = computed(() => settingsStore.isSettingsLoading);
const animationsEnabled = computed(() => settingsStore.animationsEnabled);

const currentColorVariant = computed(() => settingsStore.settingsDraft.ui.color_variant || 'slate');

// ── Kategorie-Navigation ─────────────────────────────────────────────────────

const settingsCategories = [
  { value: 'appearance', label: 'Darstellung', icon: 'mdi-palette-outline' },
  { value: 'documents', label: 'Dokumente', icon: 'mdi-file-document-outline' },
  { value: 'ai', label: 'KI & Texterkennung', icon: 'mdi-robot-outline' },
  { value: 'controls', label: 'Bedienung', icon: 'mdi-keyboard-outline' }
];

const activeCategory = ref('appearance');

// ── Konstanten ───────────────────────────────────────────────────────────────

const themeModeOptions = [
  { label: 'Hell', value: 'light' },
  { label: 'Dunkel', value: 'dark' },
  { label: 'System', value: 'system' }
];

const sortOrderOptions = [
  { label: 'Neueste zuerst', value: 'newest' },
  { label: 'Älteste zuerst', value: 'oldest' },
  { label: 'Name A–Z', value: 'name_asc' },
  { label: 'Name Z–A', value: 'name_desc' },
  { label: 'Zuletzt geöffnet', value: 'last_opened' }
];

const recentImportWindowOptions = [
  { label: '1 Stunde', value: 1 },
  { label: '6 Stunden', value: 6 },
  { label: '24 Stunden', value: 24 },
  { label: '3 Tage', value: 72 },
  { label: '7 Tage', value: 168 }
];

const trashRetentionOptions = [
  { label: 'Nie automatisch', value: 0 },
  { label: 'Nach 1 Tag', value: 1 },
  { label: 'Nach 7 Tagen', value: 7 },
  { label: 'Nach 14 Tagen', value: 14 },
  { label: 'Nach 30 Tagen', value: 30 },
  { label: 'Nach 90 Tagen', value: 90 }
];

const THEME_MODE_VALUES = new Set(['light', 'dark', 'system']);
const COLOR_VARIANT_VALUES = new Set(['indigo', 'forest', 'teal', 'slate', 'stone']);
const SETTINGS_SORT_ORDER_VALUES = new Set(['newest', 'oldest', 'name_asc', 'name_desc', 'last_opened']);
const RECENT_IMPORT_WINDOW_VALUES = new Set(recentImportWindowOptions.map((e) => e.value));
const TRASH_RETENTION_VALUES = new Set(trashRetentionOptions.map((e) => e.value));

const ocrDocLangOptions = [
  { title: 'Deutsch (Standard)', value: 'de' },
  { title: 'Englisch', value: 'en' },
  { title: 'Automatisch erkennen', value: 'auto' },
  { title: 'Mehrsprachig', value: 'multi' }
];

const OCR_DOC_LANG_VALUES = new Set(ocrDocLangOptions.map((e) => e.value));


// ── Theme ────────────────────────────────────────────────────────────────────

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(mode) {
  theme.global.name.value = resolveThemeName(mode);
}

// ── Shared save helper ───────────────────────────────────────────────────────

async function patchSettingsWithRevert({ patch, controlKey, revert }) {
  try {
    const saved = await settingsStore.saveSettingPatch(getBaseUrl(), { patch, controlKey });
    return saved !== false;
  } catch (error) {
    if (typeof revert === 'function') revert();
    notifyError(error, 'Konnte Einstellung nicht speichern.');
    return false;
  }
}

// ── Theme-Modus ──────────────────────────────────────────────────────────────

function stepThemeMode(step) {
  const ordered = themeModeOptions.map((e) => e.value);
  const currentIndex = ordered.indexOf(settingsDraft.ui.theme_mode);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;
  const nextIndex = (safeIndex + step + ordered.length) % ordered.length;
  void onThemeModeChange(ordered[nextIndex]);
}

function handleThemeModeShortcut(event) {
  if (handleShortcut(event, SHORTCUT_ACTIONS.STEP_PREVIOUS, () => stepThemeMode(-1), { ignoreEditable: false })) {
    return;
  }
  handleShortcut(event, SHORTCUT_ACTIONS.STEP_NEXT, () => stepThemeMode(1), { ignoreEditable: false });
}

function handleSettingRowShortcut(event, handler) {
  handleShortcut(event, SHORTCUT_ACTIONS.ACTIVATE, handler, { ignoreEditable: false });
}

async function onThemeModeChange(nextValue) {
  if (isSettingSaving.theme_mode) return;
  const nextMode = THEME_MODE_VALUES.has(String(nextValue)) ? String(nextValue) : 'system';
  if (nextMode === settingsDraft.ui.theme_mode) return;
  const previousMode = settingsDraft.ui.theme_mode;
  settingsStore.setDraftPatch({ ui: { theme_mode: nextMode } });
  applyTheme(nextMode);
  await patchSettingsWithRevert({
    patch: buildThemeModePatch(nextMode),
    controlKey: 'theme_mode',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { theme_mode: previousMode } });
      applyTheme(previousMode);
    }
  });
}

// ── Farbvariante ─────────────────────────────────────────────────────────────

const colorVariantOptions = [
  { label: 'Steingrau', value: 'stone', color: '#57534E' },
  { label: 'Schieferblau', value: 'slate', color: '#475569' },
  { label: 'Indigo', value: 'indigo',  color: '#2563EB' },
  { label: 'Waldgrün', value: 'forest',  color: '#16A34A' },
  { label: 'Teal',  value: 'teal',   color: '#0F766E' }
];

async function onColorVariantChange(nextValue) {
  if (isSettingSaving.color_variant) return;
  const nextVariant = COLOR_VARIANT_VALUES.has(String(nextValue)) ? String(nextValue) : 'slate';
  if (nextVariant === currentColorVariant.value) return;
  const previousVariant = currentColorVariant.value;
  settingsStore.setDraftPatch({ ui: { color_variant: nextVariant } });
  await patchSettingsWithRevert({
    patch: buildColorVariantPatch(nextVariant),
    controlKey: 'color_variant',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { color_variant: previousVariant } });
    }
  });
}

// ── Auto-OCR ─────────────────────────────────────────────────────────────────

async function onAutoOcrChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_ocr) return;
  const previous = settingsDraft.documents.auto_ocr;
  settingsStore.setDraftPatch({ documents: { auto_ocr: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoOcrPatch(nextBool),
    controlKey: 'auto_ocr',
    revert: () => settingsStore.setDraftPatch({ documents: { auto_ocr: previous } })
  });
}

function toggleAutoOcrFromRow() {
  if (isSettingSaving.auto_ocr) return;
  void onAutoOcrChange(!settingsDraft.documents.auto_ocr);
}

// ── Ollama ───────────────────────────────────────────────────────────────────

const ollamaModelPresets = [
  'llama3.2:1b',
  'llama3.2:3b',
  'llama3.1:8b',
  'phi3.5:mini',
  'mistral:7b',
  'gemma2:2b',
];

const ollamaMaxCharsOptions = [
  { label: '400 Zeichen (sehr schnell)', value: 400 },
  { label: '800 Zeichen (empfohlen)', value: 800 },
  { label: '1600 Zeichen (detaillierter)', value: 1600 },
  { label: '3200 Zeichen (langsam)', value: 3200 },
];

async function onOllamaEnabledChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ollama.enabled) return;
  const previous = settingsDraft.ollama.enabled;
  settingsStore.setDraftPatch({ ollama: { enabled: nextBool } });
  await patchSettingsWithRevert({
    patch: { ollama: { enabled: nextBool } },
    controlKey: 'ollama_enabled',
    revert: () => settingsStore.setDraftPatch({ ollama: { enabled: previous } })
  });
}

function toggleOllamaEnabledFromRow() {
  if (isSettingSaving.ollama_enabled) return;
  void onOllamaEnabledChange(!settingsDraft.ollama.enabled);
}

async function onOllamaBaseUrlChange(nextValue) {
  const url = String(nextValue || '').trim() || 'http://localhost:11434';
  if (url === settingsDraft.ollama.base_url) return;
  const previous = settingsDraft.ollama.base_url;
  settingsStore.setDraftPatch({ ollama: { base_url: url } });
  await patchSettingsWithRevert({
    patch: { ollama: { base_url: url } },
    controlKey: 'ollama_base_url',
    revert: () => settingsStore.setDraftPatch({ ollama: { base_url: previous } })
  });
}

async function onOllamaModelChange(nextValue) {
  const model = String(nextValue || '').trim() || 'llama3.2:3b';
  if (model === settingsDraft.ollama.model) return;
  const previous = settingsDraft.ollama.model;
  settingsStore.setDraftPatch({ ollama: { model } });
  await patchSettingsWithRevert({
    patch: { ollama: { model } },
    controlKey: 'ollama_model',
    revert: () => settingsStore.setDraftPatch({ ollama: { model: previous } })
  });
}

async function onOllamaMaxInputCharsChange(nextValue) {
  const chars = Number(nextValue) || 800;
  if (chars === settingsDraft.ollama.max_input_chars) return;
  const previous = settingsDraft.ollama.max_input_chars;
  settingsStore.setDraftPatch({ ollama: { max_input_chars: chars } });
  await patchSettingsWithRevert({
    patch: { ollama: { max_input_chars: chars } },
    controlKey: 'ollama_max_input_chars',
    revert: () => settingsStore.setDraftPatch({ ollama: { max_input_chars: previous } })
  });
}

// ── Auto-Tagging ─────────────────────────────────────────────────────────────

async function onAutoTaggingChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_tagging) return;
  const previous = settingsDraft.documents.auto_tagging;
  settingsStore.setDraftPatch({ documents: { auto_tagging: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoTaggingPatch(nextBool),
    controlKey: 'auto_tagging',
    revert: () => settingsStore.setDraftPatch({ documents: { auto_tagging: previous } })
  });
}

function toggleAutoTaggingFromRow() {
  if (isSettingSaving.auto_tagging) return;
  void onAutoTaggingChange(!settingsDraft.documents.auto_tagging);
}

// ── Sortierung ───────────────────────────────────────────────────────────────

async function onSortOrderChange(nextValue) {
  if (isSettingSaving.sort_order) return;
  const nextSortOrder = SETTINGS_SORT_ORDER_VALUES.has(String(nextValue))
    ? String(nextValue)
    : settingsDraft.documents.sort_order;
  if (nextSortOrder === settingsDraft.documents.sort_order) return;
  const previous = settingsDraft.documents.sort_order;
  settingsStore.setDraftPatch({ documents: { sort_order: nextSortOrder } });
  await patchSettingsWithRevert({
    patch: buildSortOrderPatch(nextSortOrder),
    controlKey: 'sort_order',
    revert: () => settingsStore.setDraftPatch({ documents: { sort_order: previous } })
  });
}

// ── Import-Zeitraum ──────────────────────────────────────────────────────────

async function onRecentImportWindowChange(nextValue) {
  if (isSettingSaving.recent_import_window_hours) return;
  const parsedHours = Number(nextValue);
  const nextHours = RECENT_IMPORT_WINDOW_VALUES.has(parsedHours)
    ? parsedHours
    : settingsDraft.documents.recent_import_window_hours;
  if (nextHours === settingsDraft.documents.recent_import_window_hours) return;
  const previous = settingsDraft.documents.recent_import_window_hours;
  settingsStore.setDraftPatch({ documents: { recent_import_window_hours: nextHours } });
  const saved = await patchSettingsWithRevert({
    patch: buildRecentImportWindowPatch(nextHours),
    controlKey: 'recent_import_window_hours',
    revert: () => settingsStore.setDraftPatch({ documents: { recent_import_window_hours: previous } })
  });
  if (saved) {
    emit('reload-imports');
  }
}

// ── Papierkorb-Aufbewahrung ────────────────────────────────────────────────

async function onTrashRetentionChange(nextValue) {
  if (isSettingSaving.trash_retention_days) return;
  const parsedDays = Number(nextValue);
  const nextDays = TRASH_RETENTION_VALUES.has(parsedDays)
    ? parsedDays
    : settingsDraft.documents.trash_retention_days;
  if (nextDays === settingsDraft.documents.trash_retention_days) return;
  const previous = settingsDraft.documents.trash_retention_days;
  settingsStore.setDraftPatch({ documents: { trash_retention_days: nextDays } });
  await patchSettingsWithRevert({
    patch: buildTrashRetentionPatch(nextDays),
    controlKey: 'trash_retention_days',
    revert: () => settingsStore.setDraftPatch({ documents: { trash_retention_days: previous } })
  });
}

// ── OCR-Sprache (Dokument-Import) ─────────────────────────────────────────────

async function onOcrDocLangChange(nextValue) {
  if (isSettingSaving.ocr_doc_lang) return;
  const nextLang = OCR_DOC_LANG_VALUES.has(String(nextValue))
    ? String(nextValue)
    : settingsDraft.documents.ocr_doc_lang;
  if (nextLang === settingsDraft.documents.ocr_doc_lang) return;
  const previous = settingsDraft.documents.ocr_doc_lang;
  settingsStore.setDraftPatch({ documents: { ocr_doc_lang: nextLang } });
  await patchSettingsWithRevert({
    patch: buildOcrDocLangPatch(nextLang),
    controlKey: 'ocr_doc_lang',
    revert: () => settingsStore.setDraftPatch({ documents: { ocr_doc_lang: previous } })
  });
}

// ── Dateiendung ──────────────────────────────────────────────────────────────

async function onShowFilenameSuffixChange(nextValue) {
  if (isSettingSaving.show_filename_suffix) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.showFilenameSuffix) return;
  const previous = settingsDraft.ui.showFilenameSuffix;
  settingsStore.setDraftPatch({ ui: { showFilenameSuffix: nextBool } });
  await patchSettingsWithRevert({
    patch: buildShowFilenameSuffixPatch(nextBool),
    controlKey: 'show_filename_suffix',
    revert: () => settingsStore.setDraftPatch({ ui: { showFilenameSuffix: previous } })
  });
}

function toggleShowFilenameSuffixFromRow() {
  if (isSettingSaving.show_filename_suffix) return;
  void onShowFilenameSuffixChange(!settingsDraft.ui.showFilenameSuffix);
}

// ── Drawer: Zustand merken ───────────────────────────────────────────────────

async function onDrawerRememberStateChange(nextValue) {
  if (isSettingSaving.drawer_remember_state) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.drawerRememberState) return;
  const previous = settingsDraft.ui.drawerRememberState;
  settingsStore.setDraftPatch({ ui: { drawerRememberState: nextBool } });
  await patchSettingsWithRevert({
    patch: buildDrawerRememberStatePatch(nextBool),
    controlKey: 'drawer_remember_state',
    revert: () => settingsStore.setDraftPatch({ ui: { drawerRememberState: previous } })
  });
}

function toggleDrawerRememberStateFromRow() {
  if (isSettingSaving.drawer_remember_state) return;
  void onDrawerRememberStateChange(!settingsDraft.ui.drawerRememberState);
}

// ── Drawer: immer ausgeklappt ────────────────────────────────────────────────

async function onDrawerAlwaysExpandedChange(nextValue) {
  if (isSettingSaving.drawer_always_expanded) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.drawerAlwaysExpanded) return;
  const previous = settingsDraft.ui.drawerAlwaysExpanded;
  settingsStore.setDraftPatch({ ui: { drawerAlwaysExpanded: nextBool } });
  await patchSettingsWithRevert({
    patch: buildDrawerAlwaysExpandedPatch(nextBool),
    controlKey: 'drawer_always_expanded',
    revert: () => settingsStore.setDraftPatch({ ui: { drawerAlwaysExpanded: previous } })
  });
}

function toggleDrawerAlwaysExpandedFromRow() {
  if (isSettingSaving.drawer_always_expanded) return;
  void onDrawerAlwaysExpandedChange(!settingsDraft.ui.drawerAlwaysExpanded);
}

// ── Animationen ──────────────────────────────────────────────────────────────

function onAnimationsEnabledChange(nextValue) {
  settingsStore.setAnimationsEnabled(Boolean(nextValue));
}

function toggleAnimationsFromRow() {
  settingsStore.setAnimationsEnabled(!settingsStore.animationsEnabled);
}
</script>
