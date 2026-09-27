import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('scanner live preview streams real PNM rows into the import dialog', async () => {
  const scanner = await readFile(
    new URL('../../deploy/scan-button/papermind-scan.sh', import.meta.url),
    'utf8',
  );
  const helper = await readFile(
    new URL('../../deploy/scan-button/papermind-live-preview.py', import.meta.url),
    'utf8',
  );
  const dialog = await readFile(
    new URL('../src/components/ImportStagingDialog.vue', import.meta.url),
    'utf8',
  );

  assert.match(scanner, /SCAN_LIVE_PREVIEW="\$\{SCAN_LIVE_PREVIEW:-true\}"/);
  assert.match(scanner, /_scan_args "\$scan_format"/);
  assert.match(scanner, /scan_format="pnm"/);
  assert.match(scanner, /papermind-live-preview\.py/);
  assert.match(helper, /available_rows/);
  assert.match(helper, /sampled_rows/);
  assert.match(helper, /write_rgb_png/);
  assert.match(helper, /\.replace\(path\)/);
  assert.match(dialog, /scannerLivePreviewUrl/);
  assert.match(dialog, /scannerLiveProgress/);
  assert.match(dialog, /isd-scanning-page-preview/);
});
