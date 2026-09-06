import assert from 'node:assert/strict';
import test from 'node:test';
import { getSchema, Node } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { TableKit } from '@tiptap/extension-table';
import { NoteAIGeneration } from '../src/components/notes/extensions/aiGeneration.js';
import { noteAIContent } from '../src/utils/noteAIContent.js';
import { noteMarkdownToSafeHtml } from '../src/utils/noteMarkdown.js';
import { noteToMarkdown } from '../src/utils/noteExport.js';

const schema = getSchema([
  StarterKit.configure({ heading: { levels: [2, 3, 4] } }), TaskList,
  TaskItem.configure({ nested: true }), TableKit, NoteAIGeneration,
  Node.create({ name: 'callout', group: 'block', content: 'block+', addAttributes: () => ({ kind: { default: 'important' } }) }),
]);
const fruit = ['Mandarine', 'Zitrone', 'Banane', 'Kiwi', 'Erdbeere', 'Himbeere', 'Brombeere', 'Blaubeere', 'Pfirsich', 'Kirsche'];
const shoppingPrompt = 'Erstelle eine Einkaufsliste mit 10 Obstsorten';
function documentFor(text, options) {
  const doc = schema.nodeFromJSON({ type: 'doc', content: noteAIContent(text, options) });
  doc.check();
  return doc;
}

test('ten shopping items become ten native unchecked tasks, even from ordinary model bullets', () => {
  for (const prefix of ['- [ ] ', '- ', '1. ']) {
    const doc = documentFor(fruit.map((name) => prefix + name).join('\n'), { instruction: shoppingPrompt });
    assert.equal(doc.firstChild.type.name, 'taskList');
    assert.equal(doc.firstChild.childCount, 10);
    doc.firstChild.forEach((item, _offset, index) => {
      assert.equal(item.type.name, 'taskItem');
      assert.equal(item.attrs.checked, false);
      assert.equal(item.textContent, fruit[index]);
    });
    assert.equal((noteToMarkdown({ title: '', body: doc.toJSON() }).match(/- \[ \]/g) || []).length, 10);
  }
});

test('check state, nested tasks and multiword entries survive generation and serialization', () => {
  const doc = documentFor('- [ ] Rote Äpfel\n  - [x] Menge prüfen\n\n- [ ] Frische Erdbeeren');
  assert.equal(doc.firstChild.childCount, 2);
  assert.equal(doc.firstChild.firstChild.firstChild.textContent, 'Rote Äpfel');
  assert.equal(doc.firstChild.firstChild.child(1).firstChild.attrs.checked, true);
  assert.deepEqual(schema.nodeFromJSON(doc.toJSON()).toJSON(), doc.toJSON());
});

test('mixed editor elements become valid native nodes with provenance', () => {
  const attribution = { prompt: 'Strukturieren', provider: 'ollama', model: 'test', generatedAt: '2026-09-06T12:00:00Z' };
  const doc = documentFor('# Plan\n\nAbsatz mit **Fettdruck**.\n\n> Zitat\n\n> [!DECISION]\n> Freigegeben\n\n```js\nconst a = 1 < 2;\n```\n\n---\n\n| Name | Anzahl |\n| --- | --- |\n| Kiwi | 3 |', { attribution });
  const types = [];
  doc.forEach((node) => { types.push(node.type.name); assert.deepEqual(node.attrs.aiGeneration, attribution); });
  assert.deepEqual(types, ['heading', 'paragraph', 'blockquote', 'callout', 'codeBlock', 'horizontalRule', 'table']);
  assert.equal(doc.firstChild.attrs.level, 2);
  assert.equal(doc.child(3).attrs.kind, 'decision');
  assert.equal(doc.child(4).textContent, 'const a = 1 < 2;');
  assert.equal(doc.child(6).firstChild.firstChild.type.name, 'tableHeader');
});

test('numbered lists preserve their start and nested bullet lists', () => {
  const doc = documentFor('3. Dritter Schritt\n   - Unterpunkt\n4. Vierter Schritt');
  assert.equal(doc.firstChild.attrs.start, 3);
  assert.equal(doc.firstChild.firstChild.child(1).type.name, 'bulletList');
});

test('explicit prose and table requests do not force a shopping list into tasks', () => {
  assert.equal(documentFor('Äpfel und Birnen.', { instruction: 'Beschreibe die Einkaufsliste als Fließtext' }).firstChild.type.name, 'paragraph');
  assert.equal(documentFor('| Obst | Menge |\n| --- | --- |\n| Apfel | 2 |', { instruction: 'Einkaufsliste als Tabelle' }).firstChild.type.name, 'table');
  assert.throws(() => documentFor(fruit.join(' '), { instruction: shoppingPrompt }), /keine Aufgabenliste/);
});

test('Markdown transport fences unwrap but code fences keep literal syntax', () => {
  assert.equal(documentFor('```markdown\n- [ ] Kiwi\n```').firstChild.type.name, 'taskList');
  assert.equal(documentFor('```txt\n- [ ] Kiwi\n```').firstChild.type.name, 'codeBlock');
});

test('generated links are allow-listed and legacy HTML rendering escapes model markup', () => {
  const doc = documentFor('[Gut](https://example.org) und [Schlecht](javascript:alert)');
  assert.equal(doc.firstChild.firstChild.marks[0].attrs.href, 'https://example.org/');
  assert.equal(doc.firstChild.lastChild.marks.length, 0);
  const html = noteMarkdownToSafeHtml('## <script>alert(1)</script>\n\n- [x] <img src=x onerror=alert(1)>\n\n[Schlecht](javascript:alert)\n\n```html\n<script>code</script>\n```');
  assert.doesNotMatch(html, /<script|<img|href="javascript:/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /type="checkbox" disabled checked/);
});
