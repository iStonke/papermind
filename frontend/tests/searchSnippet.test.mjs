import assert from 'node:assert/strict';
import test from 'node:test';

import { formatSearchSnippet } from '../src/utils/searchSnippet.js';

test('renders only exact search highlight tags as markup', () => {
  assert.equal(
    formatSearchSnippet('Kfz-<mark>Rechnung</mark> & <img src=x onerror=alert(1)>'),
    'Kfz-<mark>Rechnung</mark> &amp; &lt;img src=x onerror=alert(1)&gt;',
  );
  assert.equal(formatSearchSnippet('<mark class="x">Text</mark>'), '&lt;mark class=&quot;x&quot;&gt;Text</mark>');
});
