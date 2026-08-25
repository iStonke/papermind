import test from "node:test";
import assert from "node:assert/strict";

import { createPinia, setActivePinia } from "pinia";
import { useSettingsStore } from "../src/stores/settings.js";

test("patchSettings normalizes an empty API base URL", async () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();
  const calls = [];
  const previousFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          ui: { theme_mode: "dark" },
          documents: {},
          llm: {},
          rag: {},
          ocr: {},
          quality: {},
          meta: { version: 1 }
        };
      }
    };
  };

  try {
    await store.patchSettings(null, { ui: { theme_mode: "dark" } });
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/settings");
  assert.equal(calls[0].options.method, "PATCH");
  assert.equal(calls[0].options.body, JSON.stringify({ ui: { theme_mode: "dark" } }));
});

test("normalizeSettingsPayload drops legacy color variants", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: { theme_mode: "light", color_variant: "violet" },
  });

  assert.equal("color_variant" in normalized.ui, false);
});

test("normalizeSettingsPayload drops legacy favorite sidebar visibility", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: { sidebar_show_favorites: false },
  });

  assert.equal("sidebar_show_favorites" in normalized.ui, false);
});

test("normalizeSettingsPayload preserves auto-open import inbox setting", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    documents: { auto_open_import_inbox: true },
  });

  assert.equal(normalized.documents.auto_open_import_inbox, true);
});

test("normalizeSettingsPayload preserves dossier sidebar visibility", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: { sidebar_show_dossiers: false },
  });

  assert.equal(normalized.ui.sidebar_show_dossiers, false);
});

test("normalizeSettingsPayload preserves note preferences", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: {
      notes_default_view: "focus",
      notes_sort_order: "created",
      notes_writing_width: "wide",
      notes_paragraph_spacing: "spacious",
      notes_font_family: "serif",
      notes_spellcheck_enabled: false,
    },
  });

  assert.equal(normalized.ui.notes_default_view, "focus");
  assert.equal(normalized.ui.notes_sort_order, "created");
  assert.equal(normalized.ui.notes_writing_width, "wide");
  assert.equal(normalized.ui.notes_paragraph_spacing, "spacious");
  assert.equal(normalized.ui.notes_font_family, "serif");
  assert.equal(normalized.ui.notes_spellcheck_enabled, false);
});

test("normalizeSettingsPayload falls back for invalid note preferences", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: {
      notes_default_view: "unknown",
      notes_sort_order: "random",
      notes_writing_width: "unlimited",
      notes_paragraph_spacing: "huge",
      notes_font_family: "comic",
    },
  });

  assert.equal(normalized.ui.notes_default_view, "remember");
  assert.equal(normalized.ui.notes_sort_order, "updated");
  assert.equal(normalized.ui.notes_writing_width, "comfortable");
  assert.equal(normalized.ui.notes_paragraph_spacing, "comfortable");
  assert.equal(normalized.ui.notes_font_family, "sans");
  assert.equal(normalized.ui.notes_spellcheck_enabled, true);
});

test("normalizeSettingsPayload keeps note text generation separate from local knowledge", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ollama: { chat_model: "local-knowledge" },
    text_generation: {
      enabled: true,
      provider: "anthropic",
      anthropic_model: "claude-test",
      system_prompt: "Eigene interne Schreibanweisung für den Notizeditor mit ausreichender Länge.",
      prompt_suggestions: [
        "  Schreibe weiter  ",
        "Fasse zusammen",
        "Formuliere sachlich",
        "Nenne offene Fragen",
        "Erstelle nächste Schritte",
        "Finde Widersprüche",
        "Dieser siebte Eintrag wird verworfen",
      ],
      note_context_chars: 7000,
      max_output_tokens: 1200,
      temperature: 0.4,
    },
  });

  assert.equal(normalized.ollama.chat_model, "local-knowledge");
  assert.equal(normalized.text_generation.provider, "anthropic");
  assert.equal(normalized.text_generation.anthropic_model, "claude-test");
  assert.match(normalized.text_generation.system_prompt, /Eigene interne Schreibanweisung/);
  assert.deepEqual(normalized.text_generation.prompt_suggestions, [
    "Schreibe weiter",
    "Fasse zusammen",
    "Formuliere sachlich",
    "Nenne offene Fragen",
    "Erstelle nächste Schritte",
    "Finde Widersprüche",
  ]);
  assert.equal(normalized.text_generation.note_context_chars, 7000);
});

test("normalizeSettingsPayload allows hiding all note prompt suggestions", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    text_generation: { prompt_suggestions: [] },
  });

  assert.deepEqual(normalized.text_generation.prompt_suggestions, []);
});

test("normalizeSettingsPayload preserves wiki trust settings", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    wiki: {
      enabled: true,
      auto_compile: false,
      llm_claim_extraction: false,
      chat_retrieval: true,
      require_review_for_chat_capture: true,
      page_limit: 9,
      claim_limit: 36,
    },
  });

  assert.deepEqual(normalized.wiki, {
    enabled: true,
    auto_compile: false,
    llm_claim_extraction: false,
    chat_retrieval: true,
    require_review_for_chat_capture: true,
    page_limit: 9,
    claim_limit: 36,
  });
});
