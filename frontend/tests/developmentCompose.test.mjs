import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const localCompose = await readFile(
  new URL('../../docker-compose.yml', import.meta.url),
  'utf8',
);
const productionCompose = await readFile(
  new URL('../../docker-compose.prod.yml', import.meta.url),
  'utf8',
);
const viteConfig = await readFile(
  new URL('../vite.config.js', import.meta.url),
  'utf8',
);

function frontendService(compose) {
  const match = compose.match(/^  frontend:\n([\s\S]*?)^  backend:/m);
  assert.ok(match, 'frontend service must be defined before backend');
  return match[1];
}

test('local frontend restarts from live Vite sources instead of a static build', () => {
  const service = frontendService(localCompose);

  assert.match(service, /dockerfile: Dockerfile\n/);
  assert.doesNotMatch(service, /Dockerfile\.prod/);
  assert.match(service, /npm ci --no-audit --no-fund/);
  assert.match(service, /npm run dev -- --host 0\.0\.0\.0 --port 5173/);
  assert.match(service, /- "\$\{FRONTEND_PORT\}:5173"/);
  assert.match(service, /- \.\/frontend:\/app/);
  assert.match(service, /- frontend_node_modules:\/app\/node_modules/);
  assert.match(service, /API_PROXY_TARGET: http:\/\/backend:\$\{BACKEND_PORT\}/);
  assert.doesNotMatch(service, /VITE_API_BASE_URL: http:\/\/backend/);
  assert.match(viteConfig, /env\.API_PROXY_TARGET\s*\|\|\s*env\.VITE_API_BASE_URL/);
});

test('production frontend remains a static nginx build', () => {
  assert.match(frontendService(productionCompose), /dockerfile: Dockerfile\.prod/);
});
