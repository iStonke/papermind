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

test("normalizeSettingsPayload preserves supported color variants", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: { theme_mode: "light", color_variant: "violet" },
  });

  assert.equal(normalized.ui.color_variant, "violet");
});

test("normalizeSettingsPayload falls back to default color variant", () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();

  const normalized = store.normalizeSettingsPayload({
    ui: { theme_mode: "light", color_variant: "neon" },
  });

  assert.equal(normalized.ui.color_variant, "teal");
});
