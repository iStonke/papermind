import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { containsLegalForm, cutAtLegalForm, legalFormKey, namesEquivalent, splitLegalForm } from '../src/utils/legalForms.js';

// Same cases as backend/tests/test_legal_forms.py, so both sides stay in sync.
const cases = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/legal_forms.json', import.meta.url), 'utf8'));

test('splits trailing legal forms like the backend', () => {
  for (const [value, base, legalForm] of cases.split) {
    assert.deepEqual(splitLegalForm(value), { base, legalForm }, value);
  }
});
test('equivalence ignores missing legal forms but not conflicting ones', () => {
  for (const [left, right, expected] of cases.equivalent) {
    assert.equal(namesEquivalent(left, right), expected, `${left} / ${right}`);
    assert.equal(namesEquivalent(right, left), expected, `${right} / ${left}`);
  }
});
test('cuts text after the first legal form', () => {
  for (const [value, expected] of cases.cut) assert.equal(cutAtLegalForm(value), expected, value);
});
test('detects legal forms as whole words', () => {
  for (const [value, expected] of cases.contains) assert.equal(containsLegalForm(value), expected, value);
});
test('key is case and unicode insensitive', () => {
  assert.equal(legalFormKey('VODAFONE GmbH'), 'vodafone');
  assert.equal(legalFormKey('Möller GmbH'), legalFormKey('Möller'));
});
test('short name drops the legal form unless it should stay visible', async () => {
  const { legalFormShortName } = await import('../src/utils/legalForms.js');
  assert.equal(legalFormShortName('Vodafone GmbH'), 'Vodafone');
  assert.equal(legalFormShortName('Vodafone GmbH', true), null);
  assert.equal(legalFormShortName('Finanzamt Kiel'), undefined);
});
