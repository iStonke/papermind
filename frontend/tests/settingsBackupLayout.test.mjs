import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/components/SettingsDialog.vue', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/components/SettingsDialog.styles.css', import.meta.url), 'utf8');
const start = source.indexOf('<section v-if="activeCategory === \'backup\'"');
const end = source.indexOf('<section v-if="activeCategory === \'system\'"', start);
const backupSection = source.slice(start, end);

test('backup settings use one compact configuration panel and one save action', () => {
  assert.ok(start >= 0 && end > start, 'backup settings section must exist');
  assert.equal((backupSection.match(/<v-expansion-panel>/g) || []).length, 1);
  assert.equal((backupSection.match(/>\s*Speichern\s*</g) || []).length, 1);
  assert.ok(backupSection.includes('class="backup-summary"'));
  assert.ok(!backupSection.includes('class="backup-card"'));
});

test('encryption warning and secondary target use progressive disclosure', () => {
  assert.ok(backupSection.includes('v-if="backup.enabled && !backup.encryption_configured"'));
  assert.ok(backupSection.includes('v-if="backup.secondary_enabled"'));
  assert.ok(backupSection.includes('v-if="backupConnectionDetailsOpen"'));
});

test('backup setup header shows the selected schedule without expanding or adding a divider', () => {
  assert.ok(backupSection.includes('class="backup-setup__head-sub">{{ backupSetupSummary }}'));
  assert.ok(source.includes('const backupSetupSummary = computed'));
  assert.match(styles, /backup-setup__head-sub[\s\S]*white-space: nowrap/);
  assert.match(styles, /v-expansion-panel--active[^}]*min-height: 44px !important/);
  assert.ok(!styles.includes('backup-setup :deep(.v-expansion-panel-text__wrapper) {\n  padding: 2px 8px 4px;\n  border-top:'));
});
