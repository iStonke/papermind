import test from 'node:test';
import assert from 'node:assert/strict';

import { suggestCorrespondent, suggestionReason } from '../src/utils/correspondentSuggestion.js';

function storeWith(items) {
  return {
    correspondents: items,
    findById: (id) => items.find((item) => item.id === id) || null,
    findByName: (name) => items.find((item) => item.name === name) || null,
  };
}

const peters = { id: 'peters', name: 'Praxis Fr. Peters', aliases: [] };
const swl = { id: 'swl', name: 'Stadtwerke Leipzig', aliases: [{ alias: 'SWL Energie' }] };
const store = storeWith([peters, swl]);

test('the backend suggestion (existing correspondent found in the text) comes before the sender', () => {
  const item = { sender: 'Dr. med. Andrea', suggestion: { correspondent_id: 'peters', name: 'Praxis Fr. Peters', matched_by: 'surname' } };
  assert.equal(suggestCorrespondent(item, store), peters);
  assert.match(suggestionReason(item, peters), /im Dokument genannt/);
});

test('without a backend suggestion the sender still matches names and aliases', () => {
  assert.equal(suggestCorrespondent({ sender: 'SWL  Energie' }, store), swl);
  assert.match(suggestionReason({ sender: 'SWL Energie' }, swl), /passt zum erkannten Absender/);
  assert.equal(suggestCorrespondent({ sender: 'Unbekannt AG' }, store), null);
});

test('a backend suggestion for a deleted correspondent is ignored', () => {
  const item = { sender: 'SWL Energie', suggestion: { correspondent_id: 'gone', name: 'Weg', matched_by: 'text' } };
  assert.equal(suggestCorrespondent(item, store), swl);
});

test('in collection mode the mentioned member wins', () => {
  const item = { sender: 'SWL Energie', suggestion: { correspondent_id: 'swl', name: 'Stadtwerke Leipzig', matched_by: 'name' } };
  assert.equal(suggestCorrespondent(item, store, { collectionMode: true, mentionedMemberId: 'peters' }), peters);
});
