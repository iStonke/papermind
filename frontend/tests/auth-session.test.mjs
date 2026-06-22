import assert from 'node:assert/strict';
import test from 'node:test';

import { createPinia, setActivePinia } from 'pinia';

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

const storage = new MemoryStorage();
globalThis.localStorage = storage;
globalThis.window = {
  localStorage: storage,
  atob: globalThis.atob,
  setTimeout: globalThis.setTimeout,
  clearTimeout: globalThis.clearTimeout,
  addEventListener() {},
  removeEventListener() {},
};

const { useAuthStore } = await import('../src/stores/auth.js');
const { getRefreshToken, getToken, setRefreshToken, setToken } = await import('../src/api/client.js');

function tokenWithExpiry(secondsFromNow) {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + secondsFromNow,
  })).toString('base64url');
  return `${payload}.signature`;
}

function userPayload() {
  return {
    id: '123e4567-e89b-12d3-a456-426614174000',
    username: 'admin',
    is_admin: true,
    is_active: true,
    created_at: new Date().toISOString(),
  };
}

test('initialize recovers an expired access token without logging out', async () => {
  setActivePinia(createPinia());
  storage.values.clear();
  setToken('expired-access-token');
  setRefreshToken('valid-refresh-token');

  const renewedAccess = tokenWithExpiry(3600);
  globalThis.fetch = async (url) => {
    if (String(url).endsWith('/api/auth/me')) {
      return new Response(
        JSON.stringify({ error: { message: 'Authentication required' } }),
        { status: 401, headers: { 'content-type': 'application/json' } },
      );
    }
    if (String(url).endsWith('/api/auth/refresh')) {
      return new Response(JSON.stringify({
        access_token: renewedAccess,
        expires_in: 3600,
        refresh_expires_in: 30 * 86400,
        token_type: 'bearer',
        user: userPayload(),
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    if (String(url).endsWith('/api/auth/file-token')) {
      return new Response(
        JSON.stringify({ token: tokenWithExpiry(300), expires_in: 300 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  const auth = useAuthStore();
  await auth.initialize();

  assert.equal(auth.isAuthenticated, true);
  assert.equal(auth.username, 'admin');
  assert.equal(getToken(), renewedAccess);
  assert.equal(getRefreshToken(), '');

  await new Promise((resolve) => setImmediate(resolve));
  auth.clearSession();
});

test('initialize upgrades an existing access-only session without logging out', async () => {
  setActivePinia(createPinia());
  storage.values.clear();
  setToken(tokenWithExpiry(3600));

  const renewedAccess = tokenWithExpiry(7200);
  globalThis.fetch = async (url) => {
    if (String(url).endsWith('/api/auth/me')) {
      return new Response(
        JSON.stringify(userPayload()),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }
    if (String(url).endsWith('/api/auth/renew')) {
      return new Response(JSON.stringify({
        access_token: renewedAccess,
        expires_in: 7200,
        refresh_expires_in: 30 * 86400,
        token_type: 'bearer',
        user: userPayload(),
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    if (String(url).endsWith('/api/auth/file-token')) {
      return new Response(
        JSON.stringify({ token: tokenWithExpiry(300), expires_in: 300 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }
    throw new Error(`Unexpected URL: ${url}`);
  };

  const auth = useAuthStore();
  await auth.initialize();

  assert.equal(auth.isAuthenticated, true);
  assert.equal(getToken(), renewedAccess);
  assert.equal(getRefreshToken(), '');

  await new Promise((resolve) => setImmediate(resolve));
  auth.clearSession();
});
