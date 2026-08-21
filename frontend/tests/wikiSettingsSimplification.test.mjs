import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentUrl = new URL('../src/components/SettingsDialog.vue', import.meta.url);
const stylesUrl = new URL('../src/components/SettingsDialog.styles.css', import.meta.url);

const source = await readFile(componentUrl, 'utf8');
const styles = await readFile(stylesUrl, 'utf8');
const start = source.indexOf('<section v-if="activeCategory === \'wiki\'"');
const end = source.indexOf('<section v-if="activeCategory === \'retention\'"', start);
const wikiSection = source.slice(start, end);

test('knowledge settings present the primary user choices in plain language', () => {
  assert.ok(start >= 0 && end > start, 'knowledge settings section should be present');
  assert.match(wikiSection, /<template #actions>[\s\S]*?:model-value="settingsDraft\.wiki\.enabled"/);
  assert.match(wikiSection, /aria-label="Wissen aktivieren"/);
  assert.match(wikiSection, /density="compact"/);
  assert.doesNotMatch(wikiSection, /@click="toggleWikiSetting\('enabled'\)"/);
  assert.match(wikiSection, />Automatisch aktuell halten</);
  assert.match(wikiSection, />Bei Antworten berücksichtigen</);
  assert.match(wikiSection, /'wiki-settings-options--disabled': !settingsDraft\.wiki\.enabled/);
  assert.doesNotMatch(wikiSection, /v-if="settingsDraft\.wiki\.enabled" class="wiki-settings-options"/);
  assert.match(wikiSection, /:disabled="!settingsDraft\.wiki\.enabled \|\| isSettingSaving\.wiki_auto_compile"/);
  assert.match(wikiSection, /:disabled="!settingsDraft\.wiki\.enabled \|\| isSettingSaving\.wiki_chat_retrieval"/);
});

test('knowledge extraction is listed directly with the other settings', () => {
  assert.match(wikiSection, />Detaillierte Fakten vorschlagen</);
  assert.match(
    wikiSection,
    /:disabled="!settingsDraft\.wiki\.enabled \|\| !settingsDraft\.ollama\.enabled \|\| isSettingSaving\.wiki_llm_claim_extraction"/
  );
  assert.doesNotMatch(wikiSection, /Erweiterte Einstellungen|showWikiAdvanced|wiki-advanced-settings/);
  assert.doesNotMatch(wikiSection, /LLM-Aussagen|Chunk-Hash|OCR-Zitat/);
});

test('knowledge settings omit the previous informational callout', () => {
  assert.doesNotMatch(wikiSection, /<v-alert/);
  assert.doesNotMatch(wikiSection, /Antworten werden niemals ungeprüft zu Fakten/);
});

test('dependent knowledge settings use compact spacing without a decorative rail', () => {
  assert.match(styles, /\.wiki-settings-options\s*\{/);
  const start = styles.indexOf('.wiki-settings-options {');
  const end = styles.indexOf('}', start);
  const optionsStyles = styles.slice(start, end);
  assert.match(optionsStyles, /margin-top: 10px/);
  assert.doesNotMatch(optionsStyles, /border-left|padding-left|margin-left/);
});
