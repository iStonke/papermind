import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentUrl = new URL('../src/components/SettingsDialog.vue', import.meta.url);
const source = await readFile(componentUrl, 'utf8');
const infoCardSource = await readFile(
  new URL('../src/components/SettingsInfoCard.vue', import.meta.url),
  'utf8',
);

const sectionStart = source.indexOf('<section v-if="activeCategory === \'local_ai\'"');
const sectionEnd = source.indexOf('<section v-if="activeCategory === \'backup\'"', sectionStart);
const localAiSection = source.slice(sectionStart, sectionEnd);
const navigationStart = source.indexOf('const settingsCategories = [');
const navigationEnd = source.indexOf('// Systemkonfigurations-Tabs', navigationStart);
const navigation = source.slice(navigationStart, navigationEnd);

test('AI providers and knowledge are sibling pages in a dedicated AI group', () => {
  assert.match(navigation, /value: 'local_ai', label: 'KI-Anbieter',[^\n]+group: 'ai'/);
  assert.match(navigation, /value: 'wiki', label: 'Wissen',[^\n]+group: 'ai'/);
  assert.match(navigation, /key: 'ai', label: 'KI'/);
});

test('AI provider settings keep local knowledge visibly separated from note text generation', () => {
  assert.ok(sectionStart >= 0 && sectionEnd > sectionStart, 'local model settings section should be present');
  assert.match(localAiSection, /title="KI-Anbieter & Modelle"/);
  assert.match(localAiSection, />Ollama verwenden</);
  assert.match(localAiSection, /:model-value="settingsDraft\.ollama\.enabled"/);
  assert.match(localAiSection, /aria-label="Lokales KI-Modell verwenden"/);
  assert.doesNotMatch(localAiSection, /density="compact"/);
  assert.match(localAiSection, /Dokumenten-Wissensdatenbank/);
  assert.match(localAiSection, /Nur lokal/);
  assert.match(localAiSection, /settingsDraft\.text_generation\.provider/);
  assert.match(source, /title: 'OpenAI API', value: 'openai'/);
  assert.match(source, /title: 'Anthropic API \(Claude\)', value: 'anthropic'/);
});

test('AI toggles use the standard inset setting-row control', () => {
  assert.match(
    localAiSection,
    /@click="toggleOllamaFromRow"[\s\S]*?>Ollama verwenden<[\s\S]*?density="comfortable"[\s\S]*?\binset\b[\s\S]*?@click\.stop/,
  );
  assert.match(
    localAiSection,
    /@click="toggleTextGenerationFromRow"[\s\S]*?>Mit KI schreiben<[\s\S]*?density="comfortable"[\s\S]*?\binset\b[\s\S]*?@click\.stop/,
  );
});

test('sticky settings info cards mask the right scroll gutter', () => {
  assert.match(infoCardSource, /\.settings-info-card::after\s*\{/);
  assert.match(infoCardSource, /right:\s*calc\(-1 \* var\(--settings-info-card-gutter\)\)/);
  assert.match(infoCardSource, /background:\s*var\(--settings-info-card-surface\)/);
});

test('document knowledge owns quality and expert settings before note text generation', () => {
  assert.match(localAiSection, /class="local-ai-settings"/);
  assert.match(localAiSection, />Qualität des Dokumentenwissens</);
  assert.match(localAiSection, />Experte</);
  assert.ok(
    localAiSection.indexOf('Qualität des Dokumentenwissens')
      < localAiSection.indexOf('Textgenerierung in Notizen'),
  );
  assert.match(
    localAiSection,
    /class="pm-settings-subhead pm-settings-subhead--separated">Textgenerierung in Notizen</,
  );
  assert.doesNotMatch(localAiSection, /<template v-if="settingsDraft\.ollama\.enabled">/);
  assert.match(localAiSection, /:disabled="!settingsDraft\.ollama\.enabled \|\| isSettingSaving\.ollama_model"/);
  assert.match(localAiSection, /class="pm-settings-disclosure"[\s\S]*?:disabled="!settingsDraft\.ollama\.enabled"/);
});

test('note text generation has an editable, persisted expert system prompt', () => {
  assert.match(localAiSection, /:aria-expanded="showTextGenerationAdvanced"/);
  assert.match(localAiSection, /v-if="showTextGenerationAdvanced"/);
  assert.match(localAiSection, />Interner Prompt für Notizen</);
  assert.match(localAiSection, /v-model="noteSystemPromptDraft"/);
  assert.match(localAiSection, /@click="saveNoteSystemPrompt"/);
  assert.match(source, /system_prompt:\s*normalizedNoteSystemPromptDraft\.value/);
  assert.match(source, /NOTE_WRITING_SYSTEM_PROMPT_DEFAULT/);
});
