import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [dashboardSource, workspaceSource, dashboardCss] = await Promise.all([
  readFile(new URL('../src/views/DashboardView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/dashboard/dashboard.css', import.meta.url), 'utf8'),
]);

test('dashboard header offers import and note creation beside customization', () => {
  assert.match(
    dashboardSource,
    /dash-head__actions[\s\S]*?Dokument importieren[\s\S]*?Notiz schreiben[\s\S]*?Anpassen/,
  );
  assert.match(dashboardSource, /@click="emit\('import-document'\)"/);
  assert.match(dashboardSource, /@click="emit\('create-note'\)"/);
  assert.match(workspaceSource, /@import-document="openImport"/);
  assert.match(workspaceSource, /@create-note="createNoteFromCommandPalette"/);
});

test('dashboard quick actions are visually distinct and responsive', () => {
  assert.match(dashboardCss, /\.dash-btn--quick\s*\{[\s\S]*?color-mix\(in srgb, var\(--pm-accent\) 10%/);
  assert.match(dashboardCss, /\.dash-btn--quick:hover\s*\{[\s\S]*?color-mix\(in srgb, var\(--pm-accent\) 16%/);
  assert.doesNotMatch(dashboardCss, /\.dash-btn--quick\s*\{[^}]*box-shadow/);
  assert.doesNotMatch(dashboardCss, /\.dash-btn--(?:import|note)\s*\{/);
  assert.match(dashboardCss, /\.dash-head__actions\s*\{[\s\S]*?flex-wrap:\s*wrap/);
});
