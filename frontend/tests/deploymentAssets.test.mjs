import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const dockerfile = await readFile(new URL('../Dockerfile.prod', import.meta.url), 'utf8');
const entrypoint = await readFile(
  new URL('../docker-entrypoint.d/40-install-frontend-assets.sh', import.meta.url),
  'utf8',
);
const recoveryModule = await readFile(
  new URL('../public/stale-client.js', import.meta.url),
  'utf8',
);

test('production image preserves old hashed assets across deployments', () => {
  assert.match(dockerfile, /COPY --from=build \/app\/dist \/opt\/papermind-dist/);
  assert.match(entrypoint, /cp -a "\$\{source_dir\}\/assets\/\." "\$\{target_dir\}\/assets\/"/);
  assert.doesNotMatch(entrypoint, /rm\s+-rf.*assets/);
});

test('stale client recovery performs a guarded cache-busted navigation', () => {
  assert.match(recoveryModule, /pm-recover/);
  assert.match(recoveryModule, /sessionStorage/);
  assert.match(recoveryModule, /location\.replace/);
});
