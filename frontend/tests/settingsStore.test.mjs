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
