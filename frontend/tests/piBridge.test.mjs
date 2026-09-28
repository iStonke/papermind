import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('Pi bridge only exposes allow-listed maintenance operations over a private Unix socket', async () => {
  const [server, client] = await Promise.all([
    readFile(new URL('../../infra/launchd/papermind-pi-bridge.py', import.meta.url), 'utf8'),
    readFile(new URL('../../scripts/pi_bridge.py', import.meta.url), 'utf8'),
  ]);

  assert.match(server, /SOCKET_PATH = Path\("\/tmp\/papermind-pi-bridge\.sock"\)/);
  assert.match(server, /os\.chmod\(SOCKET_PATH, 0o600\)/);
  assert.match(server, /"status"/);
  assert.match(server, /"scanner_status"/);
  assert.match(server, /"scanner_calibration_test"/);
  assert.match(server, /"scanner_calibration_restore"/);
  assert.match(server, /"scanner_timing_test"/);
  assert.match(server, /"scanner_timing_restore"/);
  assert.match(server, /"scanner_jpeg_test"/);
  assert.match(server, /"scanner_jpeg_restore"/);
  assert.match(server, /power\/control/);
  assert.match(server, /papermind-scanner-usb-awake\.service/);
  assert.match(server, /scanimage -V/);
  assert.match(server, /active scanner options/);
  assert.match(server, /SCAN_CALIBRATE:-Never/);
  assert.match(server, /papermind-calibration-test\.bak/);
  assert.match(server, /SCANNER_SCRIPT_SOURCE/);
  assert.match(server, /ACTION_INPUT_PATHS/);
  assert.match(server, /SSH_ARGS\[0\], "-T"/);
  assert.match(server, /papermind-timing-test\.bak/);
  assert.match(server, /papermind-jpeg-test\.bak/);
  assert.match(server, /def _coerce_text/);
  assert.match(server, /except BrokenPipeError/);
  assert.match(server, /"restore_drill"/);
  assert.match(server, /"recovery_check"/);
  assert.match(server, /"quiet_fan_profile"/);
  assert.doesNotMatch(server, /request\.get\("command"\)/);
  assert.match(client, /VALID_ACTIONS/);
  assert.match(client, /"scanner_status"/);
  assert.match(client, /"scanner_calibration_test"/);
  assert.match(client, /"scanner_calibration_restore"/);
  assert.match(client, /"scanner_timing_test"/);
  assert.match(client, /"scanner_timing_restore"/);
  assert.match(client, /"scanner_jpeg_test"/);
  assert.match(client, /"scanner_jpeg_restore"/);
  assert.match(client, /Unsupported bridge action|Usage:/);
});
