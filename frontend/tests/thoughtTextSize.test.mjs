import test from 'node:test';
import assert from 'node:assert/strict';
import { resizeThoughtText } from '../src/utils/thoughtTextSize.js';
test('moving a card does not reset its textarea height; text and width changes still resize', () => {
  let writes = 0;
  const input = { value:'Gedanke', clientWidth:238, scrollHeight:23, style:{ set height(value) { writes++; this.result = value; } } };
  resizeThoughtText(input);
  assert.equal(writes,2);
  resizeThoughtText(input);
  assert.equal(writes,2);
  input.value += '\nZweite Zeile'; input.scrollHeight = 45;
  resizeThoughtText(input);
  assert.equal(input.style.result,'45px');
  input.clientWidth = 200;
  resizeThoughtText(input);
  assert.equal(writes,6);
});
