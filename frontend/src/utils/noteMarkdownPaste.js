import { noteMarkdownToTipTap } from './noteMarkdown.js';

/**
 * Erkennung für eingefügten Markdown-Rohtext (ChatGPT, GitHub, Editoren).
 * Bewusst zurückhaltend: Normaler Fließtext mit vereinzelten Sternchen oder
 * Bindestrichen soll unverändert eingefügt werden.
 */
const BLOCK_SIGNALS = [
  /^\s{0,3}#{1,6}\s+\S/m, // Überschrift
  /^\s{0,3}(?:`{3,}|~{3,})/m, // Code-Zaun
  /^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\]\s/m, // Aufgabenliste
  /^\s{0,3}>\s?\S/m, // Zitat
  /^\s{0,3}(?:\$\$|\\\[)/m, // Formelblock
  /^\s*\|.*\|\s*\n\s*\|?\s*:?-{3,}/m, // Tabelle
];
const INLINE_SIGNALS = [
  /\*\*[^*\n]+\*\*/, // fett
  /\[[^\]\n]+\]\([^\s)]+\)/, // Link
  /`[^`\n]+`/, // Code
  /~~[^~\n]+~~/, // durchgestrichen
  /(?<![\p{L}\p{N}$\\])\$[^\s$](?:[^$\n]*?[^\s$\\])?\$(?![\p{N}$])/u, // $Formel$
  /\\\(.+?\\\)/, // \(Formel\)
];
const LIST_LINE = /^\s*(?:[-*+]|\d+[.)])\s+\S/gm;

// Bringt der Browser bereits strukturiertes HTML mit (Webseiten, gerendertes
// ChatGPT), übernimmt die normale HTML-Einfügelogik. Editoren wie VS Code
// liefern nur gestylte <div>/<span> – dort zählt der Markdown-Rohtext.
const SEMANTIC_HTML = /<(?:h[1-6]|ul|ol|li|strong|b|em|i|table|pre|blockquote|code|a)[\s>]/i;

export function looksLikeMarkdown(text) {
  const value = String(text || '');
  if (!value.trim()) return false;
  if (BLOCK_SIGNALS.some((pattern) => pattern.test(value))) return true;
  if (INLINE_SIGNALS.some((pattern) => pattern.test(value))) return true;
  return (value.match(LIST_LINE) || []).length >= 2;
}

export function shouldConvertPastedMarkdown({ text, html = '' } = {}) {
  if (html && SEMANTIC_HTML.test(html)) return false;
  return looksLikeMarkdown(text);
}

/**
 * TipTap-Inhalt für das Einfügen. Ein einzelner Absatz wird als Inline-Inhalt
 * geliefert, damit er sich in den aktuellen Absatz einfügt statt ihn zu teilen.
 */
export function pastedMarkdownContent(text) {
  const blocks = noteMarkdownToTipTap(text);
  if (blocks.length === 1 && blocks[0].type === 'paragraph') return blocks[0].content || [];
  return blocks;
}
