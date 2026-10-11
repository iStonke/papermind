/**
 * Textstatistik einer Notiz (oder einer Markierung) direkt aus dem
 * ProseMirror-Dokument. Wird nur beim Öffnen des Statistik-Popovers berechnet,
 * nicht pro Anschlag.
 */

export const READING_WPM = 220;
export const SPEAKING_WPM = 145;
/** Ab dieser Wortzahl sind Lesbarkeitswerte halbwegs aussagekräftig. */
export const READABILITY_MIN_WORDS = 30;
const LONG_WORD_MIN_LETTERS = 7;
// Code ist kein Fließtext und würde Satz- und Lesbarkeitswerte verzerren.
const SKIPPED_BLOCKS = new Set(['codeBlock']);

// Abkürzungen, nach deren Punkt kein Satz endet (kleingeschrieben, ohne Punkt).
const ABBREVIATIONS = new Set([
  'abb', 'abs', 'allg', 'art', 'bd', 'bspw', 'bzgl', 'bzw', 'ca', 'chr', 'dr', 'etc', 'evtl',
  'ggf', 'gem', 'hr', 'hrsg', 'inkl', 'jh', 'kap', 'max', 'min', 'mio', 'mrd', 'nr', 'prof',
  'sog', 'st', 'str', 'tab', 'usw', 'vgl', 'zb', 'zzgl', 'fr', 'geb', 'gest', 'ff',
]);

const sentenceSegmenter = typeof Intl !== 'undefined' && Intl.Segmenter
  ? new Intl.Segmenter('de', { granularity: 'sentence' })
  : null;
const wordSegmenter = typeof Intl !== 'undefined' && Intl.Segmenter
  ? new Intl.Segmenter('de', { granularity: 'word' })
  : null;

/**
 * Text je Textblock samt Abbildung Zeichenindex → Dokumentposition. Inline-Atome
 * (Chips, Zeilenumbrüche) zählen als ein Leerzeichen.
 */
function collectBlocks(doc, from, to) {
  const blocks = [];
  doc.nodesBetween(from, to, (node, pos) => {
    if (SKIPPED_BLOCKS.has(node.type.name)) return false;
    if (!node.isTextblock) return true;
    let text = '';
    const positions = [];
    node.forEach((child, offset) => {
      const childPos = pos + 1 + offset;
      if (child.isText) {
        for (let i = 0; i < child.text.length; i += 1) {
          const charPos = childPos + i;
          if (charPos < from || charPos >= to) continue;
          text += child.text[i];
          positions.push(charPos);
        }
      } else if (childPos >= from && childPos < to) {
        text += ' ';
        positions.push(childPos);
      }
    });
    if (text.trim()) blocks.push({ text, positions });
    return false;
  });
  return blocks;
}

function endsWithAbbreviation(segment) {
  const match = segment.trimEnd().match(/(?:^|[\s(„"'])([\p{L}\d]+)\.$/u);
  if (!match) return false;
  const token = match[1].toLowerCase();
  // Einzelbuchstaben (z. B., d. h.) und Ordinalzahlen (3. Oktober).
  return /^\p{L}$/u.test(token) || /^\d{1,2}$/.test(token) || ABBREVIATIONS.has(token);
}

/** Sätze eines Textblocks als [start, end)-Bereiche; korrigiert Abkürzungsbrüche. */
export function splitSentences(text) {
  const raw = sentenceSegmenter
    ? [...sentenceSegmenter.segment(text)].map(s => ({ start: s.index, end: s.index + s.segment.length }))
    : [...text.matchAll(/[^.!?]+(?:[.!?]+|$)\s*/gu)].map(m => ({ start: m.index, end: m.index + m[0].length }));
  const merged = [];
  for (const range of raw) {
    const prev = merged[merged.length - 1];
    const startsLower = /^\s*\p{Ll}/u.test(text.slice(range.start, range.end));
    if (prev && (endsWithAbbreviation(text.slice(prev.start, prev.end)) || startsLower)) {
      prev.end = range.end;
    } else {
      merged.push({ ...range });
    }
  }
  return merged.filter(r => /[\p{L}\d]/u.test(text.slice(r.start, r.end)));
}

/** Wörter mit mindestens einem Buchstaben (für Lesbarkeit und Wortschatz). */
function letterWords(text) {
  if (wordSegmenter) {
    return [...wordSegmenter.segment(text)]
      .filter(s => s.isWordLike && /\p{L}/u.test(s.segment))
      .map(s => s.segment);
  }
  return text.match(/[\p{L}\p{M}'’-]*\p{L}[\p{L}\p{M}'’-]*/gu) || [];
}

/** Grobe deutsche Silbenzählung über Vokalgruppen (ie, ei, au … zählen einfach). */
export function countSyllables(word) {
  const groups = word.toLowerCase().match(/[aeiouyäöü]+/g);
  return Math.max(1, groups ? groups.length : 0);
}

/** Flesch-Lesbarkeitsindex nach Amstad (deutsche Anpassung), 0–100. */
export function fleschAmstad(words, sentences, syllables) {
  if (!words || !sentences) return null;
  const score = 180 - words / sentences - 58.5 * (syllables / words);
  return Math.round(Math.min(100, Math.max(0, score)));
}

export function readabilityBand(score) {
  if (score === null || score === undefined) return null;
  if (score >= 70) return { key: 'easy', label: 'leicht lesbar' };
  if (score >= 50) return { key: 'medium', label: 'mittelschwer' };
  if (score >= 30) return { key: 'hard', label: 'anspruchsvoll' };
  return { key: 'very-hard', label: 'schwer lesbar' };
}

/** Minuten für eine Wortzahl, mindestens 1, sobald Text vorhanden ist. */
export function minutesFor(words, wpm) {
  return words ? Math.max(1, Math.round(words / wpm)) : 0;
}

/**
 * @param {import('@tiptap/pm/model').Node} doc
 * @param {{from?: number, to?: number}} [range] optional nur eine Markierung
 */
export function computeNoteStats(doc, range = {}) {
  const from = Math.max(0, range.from ?? 0);
  const to = Math.min(doc.content.size, range.to ?? doc.content.size);
  const blocks = collectBlocks(doc, from, to);

  let words = 0;
  let characters = 0;
  let charactersNoSpaces = 0;
  let sentences = 0;
  let syllables = 0;
  let letters = 0;
  let longWords = 0;
  let lexicalWords = 0;
  let longest = null;
  const vocabulary = new Set();

  for (const block of blocks) {
    const { text, positions } = block;
    const trimmed = text.trim();
    words += trimmed.split(/\s+/u).length;
    characters += trimmed.length;
    charactersNoSpaces += trimmed.replace(/\s+/gu, '').length;

    for (const sentence of splitSentences(text)) {
      sentences += 1;
      const sentenceText = text.slice(sentence.start, sentence.end).trim();
      const sentenceWords = sentenceText.split(/\s+/u).length;
      if (!longest || sentenceWords > longest.words) {
        const startIndex = sentence.start + (text.slice(sentence.start).length - text.slice(sentence.start).trimStart().length);
        const endIndex = startIndex + sentenceText.length - 1;
        longest = {
          words: sentenceWords,
          text: sentenceText,
          from: positions[startIndex],
          to: positions[endIndex] + 1,
        };
      }
    }

    for (const word of letterWords(text)) {
      lexicalWords += 1;
      syllables += countSyllables(word);
      const letterCount = (word.match(/\p{L}/gu) || []).length;
      letters += letterCount;
      if (letterCount >= LONG_WORD_MIN_LETTERS) longWords += 1;
      vocabulary.add(word.toLocaleLowerCase('de'));
    }
  }

  const readabilityScore = lexicalWords >= READABILITY_MIN_WORDS
    ? fleschAmstad(lexicalWords, sentences, syllables)
    : null;

  return {
    selection: range.from !== undefined || range.to !== undefined,
    words,
    characters,
    charactersNoSpaces,
    sentences,
    paragraphs: blocks.length,
    readingMinutes: minutesFor(words, READING_WPM),
    speakingMinutes: minutesFor(words, SPEAKING_WPM),
    avgSentenceWords: sentences ? words / sentences : 0,
    longestSentence: longest,
    avgWordLetters: lexicalWords ? letters / lexicalWords : 0,
    longWordShare: lexicalWords ? longWords / lexicalWords : 0,
    uniqueWords: vocabulary.size,
    lexicalDiversity: lexicalWords ? vocabulary.size / lexicalWords : 0,
    readability: readabilityScore,
    readabilityBand: readabilityBand(readabilityScore),
  };
}
