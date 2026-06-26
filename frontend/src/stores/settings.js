import { defineStore } from 'pinia';
import {
  ANSWER_PROMPT_TEMPLATE_DEFAULT,
  NUMERIC_PROMPT_TEMPLATE_DEFAULT,
  SUMMARY_PROMPT_TEMPLATE_DEFAULT,
  SYSTEM_PROMPT_DEFAULT
} from '../constants/promptDefaults.js';
import { normalizeSidebarSections } from '../utils/settingsApi.js';

const THEME_MODE_VALUES = new Set(['light', 'dark', 'system']);
const COLOR_VARIANT_VALUES = new Set(['teal', 'violet', 'blue']);
const SORT_ORDER_VALUES = new Set([
  'newest',
  'oldest',
  'document_date_desc',
  'document_date_asc',
  'name_asc',
  'name_desc',
  'last_opened'
]);
const OCR_ENGINE_VALUES = new Set(['tesseract', 'paddleocr', 'easyocr', 'abbyy']);
const OCR_DOC_LANG_VALUES = new Set(['de', 'en', 'auto', 'multi']);
const EMBEDDING_MODEL_FALLBACK = 'hash-384-v1';
const DRAWER_EXPANDED_STORAGE_KEY  = 'pm.drawerExpanded';
const DRAWER_HEIGHT_STORAGE_KEY    = 'pm.drawerHeight';
const DRAWER_HEIGHT_DEFAULT        = 320;
const DRAWER_HEIGHT_MIN            = 180;
const DRAWER_HEIGHT_MAX            = 720;
const TAG_DRAWER_EXPANDED_STORAGE_KEY = 'pm.tagFilterDrawerExpanded';
const ANIMATIONS_ENABLED_STORAGE_KEY = 'pm.animationsEnabled';
const SCAN_ANIMATION_ENABLED_STORAGE_KEY = 'pm.scanAnimationEnabled';

function toInt(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.round(parsed);
}

function toNumber(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function clamp(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    return fallback;
  }
  return parsed;
}

function clampInt(value, min, max, fallback) {
  const parsed = toInt(value, Number.NaN);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    return fallback;
  }
  return parsed;
}

function normalizePrompt(rawValue, fallback, minLength = 50) {
  const normalized = String(rawValue ?? '')
    .replace(/\r\n/g, '\n')
    .trim();
  if (normalized.length < minLength) {
    return fallback;
  }
  return normalized;
}

function normalizeString(rawValue, fallback, minLength = 1) {
  const normalized = String(rawValue ?? '').trim();
  if (normalized.length < minLength) {
    return fallback;
  }
  return normalized;
}

function normalizeApiBaseUrl(apiBaseUrl) {
  return String(apiBaseUrl || '').replace(/\/$/, '');
}

function createDefaultSettings() {
  return {
    ui: {
      theme_mode: 'system',
      color_variant: 'teal',
      showFilenameSuffix: true,
      drawerRememberState: true,
      tagDrawerRememberState: true,
      sidebar_show_recent: true,
      sidebar_show_untagged: true,
      sidebar_show_no_text: true,
      sidebar_show_chat: true,
      sidebar_sections: normalizeSidebarSections(null),
      sidebar_max_tags: 5,
      sidebar_max_categories: 5
    },
    documents: {
      auto_ocr: true,
      auto_tagging: false,
      ocr_backfill_enabled: true,
      auto_open_import_inbox: false,
      sort_order: 'newest',
      recent_import_window_hours: 24,
      trash_retention_days: 30,
      ocr_doc_lang: 'de'
    },
    llm: {
      system_prompt: SYSTEM_PROMPT_DEFAULT,
      answer_prompt_template: ANSWER_PROMPT_TEMPLATE_DEFAULT,
      summary_prompt_template: SUMMARY_PROMPT_TEMPLATE_DEFAULT,
      numeric_prompt_template: NUMERIC_PROMPT_TEMPLATE_DEFAULT,
      temperature: 0.15,
      top_p: 0.9,
      max_output_tokens: 1200,
      embedding_model_name: EMBEDDING_MODEL_FALLBACK
    },
    rag: {
      top_k: 8,
      min_score: 0.0,
      max_context_chars: 12000,
      chunk_chars: 4500,
      chunk_overlap_chars: 600,
      rerank_enabled: false,
      rerank_top_k: 20,
      rerank_final_k: 8
    },
    ocr: {
      engine: 'tesseract',
      language: 'deu+eng',
      enable_layout: true,
      enable_table_detection: true,
      deskew: true,
      denoise: true,
      use_unpaper: true,
      dpi_target: 300,
      postprocess_hyphenation: true,
      remove_headers_footers: true
    },
    ollama: {
      enabled: true,
      base_url: 'http://host.docker.internal:11434',
      model: 'llama3.2:3b',
      chat_model: 'llama3.2:3b',
      timeout_seconds: 90,
      max_input_chars: 1500
    },
    quality: {
      enable_answer_checks: true,
      enable_self_critique: false
    },
    meta: {
      version: 1,
      updated_at: null
    }
  };
}

function cloneUi(uiValue) {
  return {
    ...uiValue,
    sidebar_sections: normalizeSidebarSections(uiValue?.sidebar_sections)
  };
}

function cloneSettings(settingsValue) {
  return {
    ui: cloneUi(settingsValue.ui),
    documents: { ...settingsValue.documents },
    llm: { ...settingsValue.llm },
    rag: { ...settingsValue.rag },
    ocr: { ...settingsValue.ocr },
    quality: { ...settingsValue.quality },
    ollama: { ...settingsValue.ollama },
    meta: { ...settingsValue.meta }
  };
}

function assignSettings(target, source) {
  Object.assign(target.ui, source.ui);
  if (source.ui && 'sidebar_sections' in source.ui) {
    target.ui.sidebar_sections = normalizeSidebarSections(source.ui.sidebar_sections);
  }
  Object.assign(target.documents, source.documents);
  Object.assign(target.llm, source.llm);
  Object.assign(target.rag, source.rag);
  Object.assign(target.ocr, source.ocr);
  Object.assign(target.quality, source.quality);
  if (source.ollama) Object.assign(target.ollama, source.ollama);
  Object.assign(target.meta, source.meta);
}

function readStoredAnimationsEnabled() {
  try {
    const raw = window.localStorage.getItem(ANIMATIONS_ENABLED_STORAGE_KEY);
    if (raw === '0') return false;
  } catch {
    // ignore
  }
  return true; // Standard: aktiviert
}

function readStoredScanAnimationEnabled() {
  try {
    const raw = window.localStorage.getItem(SCAN_ANIMATION_ENABLED_STORAGE_KEY);
    if (raw === '0') return false;
  } catch {
    // ignore
  }
  return true; // Standard: aktiviert
}

function readStoredDrawerExpanded() {
  try {
    const raw = window.localStorage.getItem(DRAWER_EXPANDED_STORAGE_KEY);
    if (raw === '1') {
      return true;
    }
    if (raw === '0') {
      return false;
    }
  } catch {
    // ignore storage access errors
  }
  return false;
}

function clampDrawerHeight(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return DRAWER_HEIGHT_DEFAULT;
  }
  return Math.round(Math.min(Math.max(parsed, DRAWER_HEIGHT_MIN), DRAWER_HEIGHT_MAX));
}

function readStoredDrawerHeight() {
  try {
    const raw = window.localStorage.getItem(DRAWER_HEIGHT_STORAGE_KEY);
    if (raw !== null) {
      return clampDrawerHeight(raw);
    }
  } catch {
    // ignore storage access errors
  }
  return DRAWER_HEIGHT_DEFAULT;
}

export const useSettingsStore = defineStore('settings', {
  state: () => {
    const defaults = createDefaultSettings();
    return {
      settings: cloneSettings(defaults),
      settingsDraft: cloneSettings(defaults),
      isSettingsLoading: false,
      isSettingSaving: {
        theme_mode: false,
        color_variant: false,
        auto_ocr: false,
        auto_tagging: false,
        ocr_backfill_enabled: false,
        auto_open_import_inbox: false,
        sort_order: false,
        recent_import_window_hours: false,
        trash_retention_days: false,
        show_filename_suffix: false,
        drawer_remember_state: false,
        tag_drawer_remember_state: false,
        sidebar_sections: false,
        sidebar_max_tags: false,
        sidebar_max_categories: false,
        prompts: false,
        reset_prompts: false
      },
      drawerExpanded: false,
      drawerLastRemembered: readStoredDrawerExpanded(),
      drawerHeight: readStoredDrawerHeight(),
      hasLoadedSettings: false,
      animationsEnabled: readStoredAnimationsEnabled(),
      scanAnimationEnabled: readStoredScanAnimationEnabled()
    };
  },
  actions: {
    setDraftPatch(patch) {
      if (patch?.ui && typeof patch.ui === 'object') {
        Object.assign(this.settingsDraft.ui, patch.ui);
      }
      if (patch?.documents && typeof patch.documents === 'object') {
        Object.assign(this.settingsDraft.documents, patch.documents);
      }
      if (patch?.llm && typeof patch.llm === 'object') {
        Object.assign(this.settingsDraft.llm, patch.llm);
      }
      if (patch?.rag && typeof patch.rag === 'object') {
        Object.assign(this.settingsDraft.rag, patch.rag);
      }
      if (patch?.ocr && typeof patch.ocr === 'object') {
        Object.assign(this.settingsDraft.ocr, patch.ocr);
      }
      if (patch?.ollama && typeof patch.ollama === 'object') {
        Object.assign(this.settingsDraft.ollama, patch.ollama);
      }
      if (patch?.quality && typeof patch.quality === 'object') {
        Object.assign(this.settingsDraft.quality, patch.quality);
      }
      if (patch?.meta && typeof patch.meta === 'object') {
        Object.assign(this.settingsDraft.meta, patch.meta);
      }
    },

    normalizeSettingsPayload(payload) {
      const defaults = createDefaultSettings();
      const rawThemeMode = String(payload?.ui?.theme_mode || '').toLowerCase();
      const rawColorVariant = String(payload?.ui?.color_variant || '').toLowerCase();
      const rawSortOrder = String(payload?.documents?.sort_order || '').toLowerCase();
      const rawRecentImportWindow = Number(payload?.documents?.recent_import_window_hours);
      const rawTrashRetentionDays = Number(payload?.documents?.trash_retention_days);
      const rawOcrEngine = String(payload?.ocr?.engine || '').toLowerCase();
      const rawOcrDocLang = String(payload?.documents?.ocr_doc_lang || '').toLowerCase();

      const chunkChars = clampInt(payload?.rag?.chunk_chars, 600, 20000, defaults.rag.chunk_chars);
      const overlapRaw = clampInt(
        payload?.rag?.chunk_overlap_chars,
        0,
        Math.max(0, chunkChars - 1),
        defaults.rag.chunk_overlap_chars
      );
      const chunkOverlapChars = overlapRaw >= chunkChars ? Math.max(0, chunkChars - 1) : overlapRaw;
      const rerankTopK = clampInt(payload?.rag?.rerank_top_k, 8, 100, defaults.rag.rerank_top_k);
      const rerankFinalK = clampInt(
        payload?.rag?.rerank_final_k,
        1,
        rerankTopK,
        Math.min(defaults.rag.rerank_final_k, rerankTopK)
      );

      return {
        ui: {
          theme_mode: THEME_MODE_VALUES.has(rawThemeMode) ? rawThemeMode : defaults.ui.theme_mode,
          color_variant: COLOR_VARIANT_VALUES.has(rawColorVariant) ? rawColorVariant : defaults.ui.color_variant,
          showFilenameSuffix:
            typeof payload?.ui?.showFilenameSuffix === 'boolean'
              ? payload.ui.showFilenameSuffix
              : defaults.ui.showFilenameSuffix,
          drawerRememberState:
            typeof payload?.ui?.drawerRememberState === 'boolean'
              ? payload.ui.drawerRememberState
              : defaults.ui.drawerRememberState,
          tagDrawerRememberState:
            typeof payload?.ui?.tagDrawerRememberState === 'boolean'
              ? payload.ui.tagDrawerRememberState
              : defaults.ui.tagDrawerRememberState,
          sidebar_show_recent:
            typeof payload?.ui?.sidebar_show_recent === 'boolean'
              ? payload.ui.sidebar_show_recent
              : defaults.ui.sidebar_show_recent,
          sidebar_show_untagged:
            typeof payload?.ui?.sidebar_show_untagged === 'boolean'
              ? payload.ui.sidebar_show_untagged
              : defaults.ui.sidebar_show_untagged,
          sidebar_show_no_text:
            typeof payload?.ui?.sidebar_show_no_text === 'boolean'
              ? payload.ui.sidebar_show_no_text
              : defaults.ui.sidebar_show_no_text,
          sidebar_show_chat:
            typeof payload?.ui?.sidebar_show_chat === 'boolean'
              ? payload.ui.sidebar_show_chat
              : defaults.ui.sidebar_show_chat,
          sidebar_sections: normalizeSidebarSections(payload?.ui?.sidebar_sections),
          sidebar_max_tags: clampInt(payload?.ui?.sidebar_max_tags, 0, 50, defaults.ui.sidebar_max_tags),
          sidebar_max_categories: clampInt(payload?.ui?.sidebar_max_categories, 0, 50, defaults.ui.sidebar_max_categories)
        },
        documents: {
          auto_ocr:
            typeof payload?.documents?.auto_ocr === 'boolean'
              ? payload.documents.auto_ocr
              : defaults.documents.auto_ocr,
          auto_tagging:
            typeof payload?.documents?.auto_tagging === 'boolean'
              ? payload.documents.auto_tagging
              : defaults.documents.auto_tagging,
          ocr_backfill_enabled:
            typeof payload?.documents?.ocr_backfill_enabled === 'boolean'
              ? payload.documents.ocr_backfill_enabled
              : defaults.documents.ocr_backfill_enabled,
          auto_open_import_inbox:
            typeof payload?.documents?.auto_open_import_inbox === 'boolean'
              ? payload.documents.auto_open_import_inbox
              : defaults.documents.auto_open_import_inbox,
          sort_order: SORT_ORDER_VALUES.has(rawSortOrder) ? rawSortOrder : defaults.documents.sort_order,
          recent_import_window_hours:
            Number.isInteger(rawRecentImportWindow) && rawRecentImportWindow > 0
              ? rawRecentImportWindow
              : defaults.documents.recent_import_window_hours,
          trash_retention_days:
            Number.isInteger(rawTrashRetentionDays) && rawTrashRetentionDays >= 0
              ? rawTrashRetentionDays
              : defaults.documents.trash_retention_days,
          ocr_doc_lang: OCR_DOC_LANG_VALUES.has(rawOcrDocLang) ? rawOcrDocLang : defaults.documents.ocr_doc_lang
        },
        llm: {
          system_prompt: normalizePrompt(payload?.llm?.system_prompt, defaults.llm.system_prompt),
          answer_prompt_template: normalizePrompt(
            payload?.llm?.answer_prompt_template,
            defaults.llm.answer_prompt_template
          ),
          summary_prompt_template: normalizePrompt(
            payload?.llm?.summary_prompt_template,
            defaults.llm.summary_prompt_template
          ),
          numeric_prompt_template: normalizePrompt(
            payload?.llm?.numeric_prompt_template,
            defaults.llm.numeric_prompt_template
          ),
          temperature: clamp(payload?.llm?.temperature, 0, 1, defaults.llm.temperature),
          top_p: clamp(payload?.llm?.top_p, 0, 1, defaults.llm.top_p),
          max_output_tokens: clampInt(
            payload?.llm?.max_output_tokens,
            256,
            4096,
            defaults.llm.max_output_tokens
          ),
          embedding_model_name: normalizeString(
            payload?.llm?.embedding_model_name,
            defaults.llm.embedding_model_name,
            3
          )
        },
        rag: {
          top_k: clampInt(payload?.rag?.top_k, 1, 50, defaults.rag.top_k),
          min_score: clamp(payload?.rag?.min_score, 0, 1, defaults.rag.min_score),
          max_context_chars: clampInt(
            payload?.rag?.max_context_chars,
            4000,
            40000,
            defaults.rag.max_context_chars
          ),
          chunk_chars: chunkChars,
          chunk_overlap_chars: chunkOverlapChars,
          rerank_enabled:
            typeof payload?.rag?.rerank_enabled === 'boolean'
              ? payload.rag.rerank_enabled
              : defaults.rag.rerank_enabled,
          rerank_top_k: rerankTopK,
          rerank_final_k: rerankFinalK
        },
        ocr: {
          engine: OCR_ENGINE_VALUES.has(rawOcrEngine) ? rawOcrEngine : defaults.ocr.engine,
          language: normalizeString(payload?.ocr?.language, defaults.ocr.language, 2).toLowerCase(),
          enable_layout:
            typeof payload?.ocr?.enable_layout === 'boolean'
              ? payload.ocr.enable_layout
              : defaults.ocr.enable_layout,
          enable_table_detection:
            typeof payload?.ocr?.enable_table_detection === 'boolean'
              ? payload.ocr.enable_table_detection
              : defaults.ocr.enable_table_detection,
          deskew: typeof payload?.ocr?.deskew === 'boolean' ? payload.ocr.deskew : defaults.ocr.deskew,
          denoise: typeof payload?.ocr?.denoise === 'boolean' ? payload.ocr.denoise : defaults.ocr.denoise,
          use_unpaper:
            typeof payload?.ocr?.use_unpaper === 'boolean'
              ? payload.ocr.use_unpaper
              : defaults.ocr.use_unpaper,
          dpi_target: clampInt(payload?.ocr?.dpi_target, 150, 600, defaults.ocr.dpi_target),
          postprocess_hyphenation:
            typeof payload?.ocr?.postprocess_hyphenation === 'boolean'
              ? payload.ocr.postprocess_hyphenation
              : defaults.ocr.postprocess_hyphenation,
          remove_headers_footers:
            typeof payload?.ocr?.remove_headers_footers === 'boolean'
              ? payload.ocr.remove_headers_footers
              : defaults.ocr.remove_headers_footers
        },
        ollama: {
          enabled: typeof payload?.ollama?.enabled === 'boolean' ? payload.ollama.enabled : defaults.ollama.enabled,
          base_url: typeof payload?.ollama?.base_url === 'string' && payload.ollama.base_url.trim()
            ? payload.ollama.base_url.trim()
            : defaults.ollama.base_url,
          model: typeof payload?.ollama?.model === 'string' && payload.ollama.model.trim()
            ? payload.ollama.model.trim()
            : defaults.ollama.model,
          chat_model: typeof payload?.ollama?.chat_model === 'string' && payload.ollama.chat_model.trim()
            ? payload.ollama.chat_model.trim()
            : defaults.ollama.chat_model,
          timeout_seconds: typeof payload?.ollama?.timeout_seconds === 'number' ? payload.ollama.timeout_seconds : defaults.ollama.timeout_seconds,
          max_input_chars: typeof payload?.ollama?.max_input_chars === 'number' ? payload.ollama.max_input_chars : defaults.ollama.max_input_chars
        },
        quality: {
          enable_answer_checks:
            typeof payload?.quality?.enable_answer_checks === 'boolean'
              ? payload.quality.enable_answer_checks
              : defaults.quality.enable_answer_checks,
          enable_self_critique:
            typeof payload?.quality?.enable_self_critique === 'boolean'
              ? payload.quality.enable_self_critique
              : defaults.quality.enable_self_critique
        },
        meta: {
          version: Math.max(1, toInt(payload?.meta?.version, defaults.meta.version)),
          updated_at:
            typeof payload?.meta?.updated_at === 'string' && payload.meta.updated_at.trim()
              ? payload.meta.updated_at.trim()
              : null
        }
      };
    },

    persistDrawerExpanded(value) {
      const normalized = Boolean(value);
      this.drawerLastRemembered = normalized;
      try {
        window.localStorage.setItem(DRAWER_EXPANDED_STORAGE_KEY, normalized ? '1' : '0');
      } catch {
        // ignore storage access errors
      }
    },

    clearPersistedDrawerExpanded() {
      try {
        window.localStorage.removeItem(DRAWER_EXPANDED_STORAGE_KEY);
      } catch {
        // ignore storage access errors
      }
    },

    readStoredTagDrawerExpanded() {
      try {
        const raw = window.localStorage.getItem(TAG_DRAWER_EXPANDED_STORAGE_KEY);
        if (raw === '1') return true;
        if (raw === '0') return false;
      } catch {
        // ignore storage access errors
      }
      return false;
    },

    persistTagDrawerExpanded(value) {
      try {
        window.localStorage.setItem(TAG_DRAWER_EXPANDED_STORAGE_KEY, Boolean(value) ? '1' : '0');
      } catch {
        // ignore storage access errors
      }
    },

    clearPersistedTagDrawerExpanded() {
      try {
        window.localStorage.removeItem(TAG_DRAWER_EXPANDED_STORAGE_KEY);
      } catch {
        // ignore storage access errors
      }
    },

    setAnimationsEnabled(value) {
      this.animationsEnabled = Boolean(value);
      try {
        window.localStorage.setItem(ANIMATIONS_ENABLED_STORAGE_KEY, this.animationsEnabled ? '1' : '0');
      } catch {
        // ignore
      }
    },

    setScanAnimationEnabled(value) {
      this.scanAnimationEnabled = Boolean(value);
      try {
        window.localStorage.setItem(SCAN_ANIMATION_ENABLED_STORAGE_KEY, this.scanAnimationEnabled ? '1' : '0');
      } catch {
        // ignore
      }
    },

    setDrawerExpanded(value, options = {}) {
      const normalized = Boolean(value);
      this.drawerExpanded = normalized;

      if (options.persist === false) {
        return;
      }
      if (this.settings.ui.drawerRememberState) {
        this.persistDrawerExpanded(normalized);
      }
    },

    toggleDrawerExpanded() {
      this.setDrawerExpanded(!this.drawerExpanded);
    },

    setDrawerHeight(value) {
      const normalized = clampDrawerHeight(value);
      this.drawerHeight = normalized;
      try {
        window.localStorage.setItem(DRAWER_HEIGHT_STORAGE_KEY, String(normalized));
      } catch {
        // ignore storage access errors
      }
    },

    initializeDrawerExpandedState() {
      if (this.settings.ui.drawerRememberState) {
        this.drawerExpanded = this.drawerLastRemembered;
        return;
      }
      this.drawerExpanded = false;
    },

    applySettingsFromBackend(payload, options = {}) {
      const previous = cloneSettings(this.settings);
      const normalized = this.normalizeSettingsPayload(payload);
      const hadLoadedSettings = this.hasLoadedSettings;

      assignSettings(this.settings, normalized);
      if (options.syncDraft !== false) {
        assignSettings(this.settingsDraft, normalized);
      }
      this.hasLoadedSettings = true;

      if (!hadLoadedSettings) {
        this.initializeDrawerExpandedState();
        return normalized;
      }

      const wasRememberState = Boolean(previous?.ui?.drawerRememberState);
      const isRememberState = Boolean(normalized.ui.drawerRememberState);

      if (wasRememberState && !isRememberState) {
        this.clearPersistedDrawerExpanded();
      } else if (!wasRememberState && isRememberState) {
        this.persistDrawerExpanded(this.drawerExpanded);
      }

      const wasTagRememberState = Boolean(previous?.ui?.tagDrawerRememberState);
      const isTagRememberState = Boolean(normalized.ui.tagDrawerRememberState);
      if (wasTagRememberState && !isTagRememberState) {
        this.clearPersistedTagDrawerExpanded();
      }

      return normalized;
    },

    async fetchSettings(apiBaseUrl, options = {}) {
      const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
      const silent = options.silent === true;
      if (!silent) {
        this.isSettingsLoading = true;
      }
      try {
        const response = await fetch(`${baseUrl}/api/settings`);
        if (!response.ok) {
          throw new Error(await this.parseResponseError(response));
        }
        const payload = await response.json();
        this.applySettingsFromBackend(payload, { syncDraft: options.syncDraft !== false });
        return this.settings;
      } finally {
        if (!silent) {
          this.isSettingsLoading = false;
        }
      }
    },

    async putSettings(apiBaseUrl, payload) {
      const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
      const response = await fetch(`${baseUrl}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      });
      if (!response.ok) {
        throw new Error(await this.parseResponseError(response));
      }
      const nextPayload = await response.json();
      this.applySettingsFromBackend(nextPayload);
      return this.settings;
    },

    async patchSettings(apiBaseUrl, patch) {
      const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
      const response = await fetch(`${baseUrl}/api/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch)
      });
      if (!response.ok) {
        throw new Error(await this.parseResponseError(response));
      }
      const payload = await response.json();
      this.applySettingsFromBackend(payload);
      return this.settings;
    },

    async savePromptSettings(apiBaseUrl, patch) {
      if (this.isSettingSaving.prompts) {
        return false;
      }
      this.isSettingSaving.prompts = true;
      try {
        await this.patchSettings(apiBaseUrl, patch);
        return true;
      } finally {
        this.isSettingSaving.prompts = false;
      }
    },

    async resetPrompts(apiBaseUrl) {
      if (this.isSettingSaving.reset_prompts) {
        return false;
      }
      this.isSettingSaving.reset_prompts = true;
      try {
        const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
        const response = await fetch(`${baseUrl}/api/settings/reset-prompts`, {
          method: 'POST'
        });
        if (!response.ok) {
          throw new Error(await this.parseResponseError(response));
        }
        const payload = await response.json();
        this.applySettingsFromBackend(payload);
        return true;
      } finally {
        this.isSettingSaving.reset_prompts = false;
      }
    },

    async saveSettingPatch(apiBaseUrl, { patch, controlKey }) {
      if (!Object.prototype.hasOwnProperty.call(this.isSettingSaving, controlKey)) {
        // Allow newly introduced controls even if an older in-memory store shape is active.
        this.isSettingSaving[controlKey] = false;
      }
      if (this.isSettingSaving[controlKey]) {
        return false;
      }

      this.isSettingSaving[controlKey] = true;
      try {
        await this.patchSettings(apiBaseUrl, patch);
        return true;
      } finally {
        this.isSettingSaving[controlKey] = false;
      }
    },

    async parseResponseError(response) {
      try {
        const payload = await response.json();
        return payload?.error?.message || `Request failed (${response.status})`;
      } catch {
        return `Request failed (${response.status})`;
      }
    }
  }
});
