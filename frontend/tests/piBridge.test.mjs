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
  assert.match(server, /"restore_drill"/);
  assert.match(server, /"recovery_check"/);
  assert.doesNotMatch(server, /request\.get\("command"\)/);
  assert.match(client, /VALID_ACTIONS/);
  assert.match(client, /Unsupported bridge action|Usage:/);
});
