import test from 'node:test';
import assert from 'node:assert/strict';
import { looksLikeMarkdown, pastedMarkdownContent, shouldConvertPastedMarkdown } from '../src/utils/noteMarkdownPaste.js';
import { noteMarkdownToTipTap, parseMarkdownInline } from '../src/utils/noteMarkdown.js';
import { noteContentToMarkdown, noteContentToPlainText } from '../src/utils/noteExport.js';

const CHATGPT = `## Rotation

Eine **Rotation** um den Ursprung:

$$
R(\\theta) = \\begin{pmatrix} \\cos\\theta & -\\sin\\theta \\\\ \\sin\\theta & \\cos\\theta \\end{pmatrix}
$$

- Winkel \\(\\theta\\) im Bogenmaß
- siehe [Wikipedia](https://de.wikipedia.org/wiki/Drehmatrix)`;

test('ChatGPT-style markdown is detected and converted into note blocks', () => {
  assert.equal(shouldConvertPastedMarkdown({ text: CHATGPT }), true);
  const types = pastedMarkdownContent(CHATGPT).map((node) => node.type);
  assert.deepEqual(types, ['heading', 'paragraph', 'blockMath', 'bulletList']);
  const [, paragraph, math, list] = pastedMarkdownContent(CHATGPT);
  assert.ok(paragraph.content.some((node) => node.marks?.[0]?.type === 'bold'));
  assert.match(math.attrs.latex, /^R\(\\theta\) = \\begin\{pmatrix\}/);
  const firstItem = list.content[0].content[0].content;
  assert.deepEqual(firstItem[1], { type: 'inlineMath', attrs: { latex: '\\theta' } });
});

test('plain prose and prices stay untouched', () => {
  assert.equal(looksLikeMarkdown('Ein ganz normaler Satz. Und noch einer.'), false);
  assert.equal(looksLikeMarkdown('Das kostet 5 $ bis 10 $ pro Monat.'), false);
  assert.equal(looksLikeMarkdown('- nur eine Zeile mit Strich'), false);
  assert.equal(looksLikeMarkdown('- erster Punkt\n- zweiter Punkt'), true);
});

test('semantic HTML wins over the markdown fallback, editor-only HTML does not', () => {
  assert.equal(shouldConvertPastedMarkdown({ text: '# Titel', html: '<h1>Titel</h1>' }), false);
  assert.equal(
    shouldConvertPastedMarkdown({ text: '# Titel', html: '<div style="color:#fff"><span># Titel</span></div>' }),
    true,
  );
});

test('a single pasted paragraph becomes inline content', () => {
  const content = pastedMarkdownContent('Das ist **wichtig** mit $x^2$');
  assert.deepEqual(content.map((node) => node.type), ['text', 'text', 'text', 'inlineMath']);
});

test('underscore emphasis only applies at word boundaries', () => {
  assert.deepEqual(parseMarkdownInline('datei_name_neu'), [{ text: 'datei_name_neu' }]);
  assert.deepEqual(parseMarkdownInline('_kursiv_'), [{ text: 'kursiv', italic: true }]);
});

test('escaped dollar signs stay literal', () => {
  assert.deepEqual(parseMarkdownInline('\\$5 und \\$10'), [{ text: '$' }, { text: '5 und ' }, { text: '$' }, { text: '10' }]);
});

test('math survives the markdown round trip used by cleanup and export', () => {
  const body = { type: 'doc', content: [
    { type: 'paragraph', content: [{ type: 'text', text: 'Winkel ' }, { type: 'inlineMath', attrs: { latex: '\\alpha' } }] },
    { type: 'blockMath', attrs: { latex: 'a^2 + b^2 = c^2' } },
  ] };
  const markdown = noteContentToMarkdown(body);
  assert.equal(markdown, 'Winkel $\\alpha$\n\n$$\na^2 + b^2 = c^2\n$$');
  assert.deepEqual(noteMarkdownToTipTap(markdown), body.content);
  assert.equal(noteContentToPlainText(body), 'Winkel \\alpha\na^2 + b^2 = c^2');
});
