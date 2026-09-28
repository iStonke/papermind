import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('scanner calibration is explicit, validated, and forwarded to SANE', async () => {
  const source = await readFile(
    new URL('../../deploy/scan-button/papermind-scan.sh', import.meta.url),
    'utf8',
  );

  assert.match(source, /SCAN_CALIBRATE="\$\{SCAN_CALIBRATE:-Once\}"/);
  assert.match(source, /auto\|Once\|Always\|Never/);
  assert.match(source, /--calibrate "\$SCAN_CALIBRATE"/);
  assert.match(source, /Phase Scanneraufnahme/);
  assert.match(source, /Phase PDF-Erzeugung/);
  assert.match(source, /Phase Vorschau/);
  assert.match(source, /SCAN_FORMAT="\$\{SCAN_FORMAT:-png\}"/);
  assert.match(source, /png\) SCAN_EXTENSION="png"/);
  assert.match(source, /jpeg\) SCAN_EXTENSION="jpg"/);
  assert.match(source, /local output_format="\$\{1:-\$SCAN_FORMAT\}"/);
  assert.match(source, /--format="\$output_format"/);
  assert.match(source, /_scan_args "\$scan_format"/);
});
