import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const settingsSource = await readFile(
  new URL('../src/components/SettingsDialog.vue', import.meta.url),
  'utf8'
);
const scannerSource = await readFile(
  new URL('../src/components/ScannerSettingsPanel.vue', import.meta.url),
  'utf8'
);
const scannerApiSource = await readFile(
  new URL('../src/api/scanners.js', import.meta.url),
  'utf8'
);

test('scanner management is a dedicated admin settings category', () => {
  assert.match(settingsSource, /value: 'scanner', label: 'Scanner'.*adminOnly: true/);
  assert.match(settingsSource, /activeCategory === 'scanner'[\s\S]*?<ScannerSettingsPanel/);

  const importStart = settingsSource.indexOf("activeCategory === 'import'");
  const categoriesStart = settingsSource.indexOf("activeCategory === 'categories'", importStart);
  const importSection = settingsSource.slice(importStart, categoriesStart);
  assert.doesNotMatch(importSection, /ScannerSettingsPanel|Seiten sofort senden/);
});

test('scanner panel splits devices into an added and an available section', () => {
  assert.match(scannerSource, /addedScanners = computed\([\s\S]*?scanner\.configured/);
  assert.match(scannerSource, /availableScanners = computed\([\s\S]*?!scanner\.configured && scanner\.available/);
  assert.match(scannerSource, /scannerSections = computed\(/);
  assert.match(scannerSource, /title: 'Hinzugefügt'/);
  assert.match(scannerSource, /title: 'Verfügbar'/);
  assert.match(scannerSource, /v-for="section in scannerSections"/);
  assert.match(scannerSource, /class="scanner-section__title"/);
  assert.match(scannerSource, /v-for="scanner in section\.scanners"/);
  assert.match(scannerSource, /role="listbox"/);
  assert.match(scannerSource, /role="option"/);
  assert.match(scannerSource, /:aria-selected="selectedScannerId === scanner\.id"/);
  // Verfügbare Geräte: Inline-„+"-Button am Item (kein separater Hinzufügen-Button unten).
  assert.match(scannerSource, /section\.key === 'added'/);
  assert.match(scannerSource, /scanner-device-row--static/);
  assert.match(scannerSource, /class="scanner-device-row__add"[\s\S]*?icon="mdi-plus"[\s\S]*?@click="addScanner\(scanner\)"/);
  assert.doesNotMatch(scannerSource, />\s*Hinzufügen\s*</);
  assert.doesNotMatch(scannerSource, />\s*Einrichten\s*</);
  // „Seiten sofort senden" ist pro Scanner (Toggle in der Konfiguration),
  // die frühere globale Scanverhalten-Sektion ist entfernt.
  assert.match(scannerSource, /Seiten sofort senden/);
  assert.match(scannerSource, /v-model="selectedScanner\.live_page_mode"/);
  assert.match(scannerSource, /live_page_mode: Boolean\(scanner\.live_page_mode\)/);
  assert.doesNotMatch(scannerSource, /scanner-behavior/);
  assert.doesNotMatch(scannerSource, /scan_live_page_mode|settingsStore/);
  assert.match(scannerSource, /setInterval\([\s\S]*?loadScanners\(\)[\s\S]*?12_000/);
});

test('scanner setup defaults to a shared inbox and keeps user access optional', () => {
  assert.doesNotMatch(scannerSource, /label="Empfänger"/);
  // „Zugriff einschränken" steht direkt in der Konfiguration - keine
  // „Erweiterte Einstellungen"-Klappe mehr.
  assert.doesNotMatch(scannerSource, /Erweiterte Einstellungen|scanner-detail__advanced|advancedOpen/);
  assert.match(scannerSource, /Zugriff einschränken/);
  assert.match(scannerSource, /label="Berechtigte Benutzer"/);
  assert.match(scannerSource, /addScanner\(scanner\)[\s\S]*?recipient_user_ids: \[\]/);
  assert.match(scannerSource, /recipient_user_ids: scanner\.access_restricted \? scanner\.recipient_user_ids : \[\]/);
});

test('scanner api exposes the explicit configure action', () => {
  assert.match(scannerApiSource, /configureScanner/);
  assert.match(scannerApiSource, /\/configure`/);
});

test('added scanners can be removed and become available again', () => {
  assert.match(scannerSource, /requestRemoveScanner\(selectedScanner\)[\s\S]*?>\s*Entfernen\s*</);
  assert.match(scannerSource, /title="Scanner entfernen\?"/);
  assert.match(scannerSource, /removeScannerConfiguration\(scanner\.id\)/);
  assert.match(scannerSource, /scanners\.value\[index\] = normalizeScanner\(saved\)/);
  assert.match(scannerApiSource, /removeScannerConfiguration/);
  assert.match(scannerApiSource, /\/configuration`/);
});
