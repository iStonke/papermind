import assert from 'node:assert/strict';
import test from 'node:test';

import {
  consumeDossierSidebarEntryAnimation,
  requestDossierSidebarEntryAnimation,
} from '../src/utils/dossierEntryAnimation.js';

test('sidebar entry animation is a one-shot request', () => {
  requestDossierSidebarEntryAnimation();
  assert.equal(consumeDossierSidebarEntryAnimation(), true);
  assert.equal(consumeDossierSidebarEntryAnimation(), false);
});

test('repeated sidebar requests still produce one clean entry animation', () => {
  requestDossierSidebarEntryAnimation();
  requestDossierSidebarEntryAnimation();

  assert.equal(consumeDossierSidebarEntryAnimation(), true);
  assert.equal(consumeDossierSidebarEntryAnimation(), false);
});
