import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentUrl = new URL('../src/components/SettingsDialog.vue', import.meta.url);
const source = await readFile(componentUrl, 'utf8');

const sectionStart = source.indexOf('<section v-if="activeCategory === \'local_ai\'"');
const sectionEnd = source.indexOf('<section v-if="activeCategory === \'backup\'"', sectionStart);
const localAiSection = source.slice(sectionStart, sectionEnd);
const navigationStart = source.indexOf('const settingsCategories = [');
const navigationEnd = source.indexOf('// Systemkonfigurations-Tabs', navigationStart);
const navigation = source.slice(navigationStart, navigationEnd);

test('local model and knowledge are sibling pages in a dedicated AI group', () => {
  assert.match(navigation, /value: 'local_ai', label: 'KI-Modell',[^\n]+group: 'ai'/);
  assert.match(navigation, /value: 'wiki', label: 'Wissen',[^\n]+group: 'ai'/);
  assert.match(navigation, /key: 'ai', label: 'KI'/);
});

test('local model activation follows the compact info-card pattern', () => {
  assert.ok(sectionStart >= 0 && sectionEnd > sectionStart, 'local model settings section should be present');
  assert.match(localAiSection, /title="KI-Modell"/);
  assert.match(localAiSection, /<template #actions>[\s\S]*?:model-value="settingsDraft\.ollama\.enabled"/);
  assert.match(localAiSection, /aria-label="KI-Modell verwenden"/);
  assert.match(localAiSection, /density="compact"/);
  assert.doesNotMatch(localAiSection, /Lokale KI \(Ollama\)|Lokale KI verwenden/);
});

test('quality and expert settings stay visible but disabled without the local model', () => {
  assert.match(localAiSection, /class="local-ai-settings"/);
  assert.match(localAiSection, />Qualität</);
  assert.match(localAiSection, />Experte</);
  assert.doesNotMatch(localAiSection, /<template v-if="settingsDraft\.ollama\.enabled">/);
  assert.match(localAiSection, /:disabled="!settingsDraft\.ollama\.enabled \|\| isSettingSaving\.ollama_model"/);
  assert.match(localAiSection, /class="pm-settings-disclosure"[\s\S]*?:disabled="!settingsDraft\.ollama\.enabled"/);
});
