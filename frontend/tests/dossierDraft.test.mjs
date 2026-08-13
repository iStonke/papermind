import test from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_DOSSIER_TITLE, shouldDiscardDossierDraft } from '../src/utils/dossierDraft.js';

test('a new dossier without a changed title is retained when it has contents', () => {
  assert.equal(shouldDiscardDossierDraft({ title: DEFAULT_DOSSIER_TITLE }, [{ id: 'item-1' }]), false);
});

test('a renamed new dossier without contents is discarded', () => {
  assert.equal(shouldDiscardDossierDraft({ title: 'Steuer 2026' }, []), true);
});

test('an untouched empty dossier is discarded', () => {
  assert.equal(shouldDiscardDossierDraft({ title: DEFAULT_DOSSIER_TITLE }, []), true);
});

test('a renamed new dossier with contents is retained', () => {
  assert.equal(shouldDiscardDossierDraft({ title: 'Steuer 2026' }, [{ id: 'item-1' }]), false);
});
