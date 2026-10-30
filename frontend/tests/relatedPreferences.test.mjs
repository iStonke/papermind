import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { normalizeRelatedPreferences, relatedProfiles } from '../src/utils/relatedPreferences.js';
import { useSettingsStore } from '../src/stores/settings.js';

test('existing settings default to balanced and normalization owns its weights', () => {
  const defaults = normalizeRelatedPreferences(null);
  defaults.weights.tags = 'high';
  assert.equal(normalizeRelatedPreferences(null).weights.tags, 'normal');
  for (const profile of relatedProfiles) {
    assert.deepEqual(normalizeRelatedPreferences({ profile: profile.value }).weights, profile.weights);
  }
});

test('custom settings normalize each feature and survive the store round trip', () => {
  setActivePinia(createPinia());
  const store = useSettingsStore();
  const preferences = { profile: 'custom', weights: { tags: 'high', series: 'invalid' } };
  const ui = store.normalizeSettingsPayload({ ui: { related_documents: preferences } }).ui;
  assert.equal(ui.related_documents.weights.tags, 'high');
  assert.equal(ui.related_documents.weights.series, 'normal');
  store.applySettingsFromBackend({ ui });
  assert.deepEqual(store.settingsDraft.ui.related_documents, normalizeRelatedPreferences(preferences));
});
