import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

const searchPluginKey = new PluginKey('paperMindNoteSearch');

function normalizedSearchText(value) {
  return String(value || '').toLocaleLowerCase('de-DE');
}

export function findNoteSearchRanges(doc, rawQuery) {
  const query = String(rawQuery || '').trim();
  if (!doc || !query) return [];
  const needle = normalizedSearchText(query);
  const ranges = [];

  doc.descendants((node, position) => {
    if (!node.isTextblock) return;
    const segments = [];
    let blockText = '';
    node.descendants((child, offset) => {
      if (!child.isText || !child.text) return;
      const value = String(child.text);
      segments.push({
        textFrom: blockText.length,
        textTo: blockText.length + value.length,
        documentFrom: position + 1 + offset,
      });
      blockText += value;
    });
    const text = normalizedSearchText(blockText);
    let offset = 0;
    while (offset <= text.length - needle.length) {
      const match = text.indexOf(needle, offset);
      if (match < 0) break;
      const from = documentPositionAtTextOffset(segments, match);
      const to = documentPositionAtTextOffset(segments, match + needle.length);
      if (Number.isInteger(from) && Number.isInteger(to) && to > from) {
        ranges.push({ from, to });
      }
      offset = match + Math.max(1, needle.length);
    }
    return false;
  });

  return ranges;
}

function documentPositionAtTextOffset(segments, textOffset) {
  for (const segment of segments) {
    if (textOffset < segment.textFrom || textOffset > segment.textTo) continue;
    return segment.documentFrom + textOffset - segment.textFrom;
  }
  return null;
}

function normalizedActiveIndex(index, count) {
  if (!count) return -1;
  const requested = Number.isInteger(index) ? index : 0;
  return ((requested % count) + count) % count;
}

function createSearchState(doc, query, requestedIndex = 0) {
  const ranges = findNoteSearchRanges(doc, query);
  const activeIndex = normalizedActiveIndex(requestedIndex, ranges.length);
  const decorations = DecorationSet.create(
    doc,
    ranges.map((range, index) => Decoration.inline(range.from, range.to, {
      class: index === activeIndex
        ? 'pm-note-search-match pm-note-search-match--active'
        : 'pm-note-search-match',
      'data-note-search-match': String(index + 1),
    })),
  );
  return { query: String(query || '').trim(), ranges, activeIndex, decorations };
}

export const NoteSearch = Extension.create({
  name: 'paperMindNoteSearch',

  addProseMirrorPlugins() {
    return [new Plugin({
      key: searchPluginKey,
      state: {
        init: (_config, state) => createSearchState(state.doc, ''),
        apply(transaction, previous, _oldState, newState) {
          const update = transaction.getMeta(searchPluginKey);
          if (update) {
            return createSearchState(
              newState.doc,
              update.query ?? previous.query,
              update.activeIndex ?? previous.activeIndex,
            );
          }
          if (transaction.docChanged && previous.query) {
            return createSearchState(
              newState.doc,
              previous.query,
              previous.activeIndex,
            );
          }
          return previous;
        },
      },
      props: {
        decorations(state) {
          return searchPluginKey.getState(state)?.decorations || DecorationSet.empty;
        },
      },
    })];
  },
});

export function setNoteSearch(editor, query, activeIndex = 0) {
  if (!editor || editor.isDestroyed) return { query: '', ranges: [], activeIndex: -1 };
  editor.view.dispatch(editor.state.tr.setMeta(searchPluginKey, { query, activeIndex }));
  return getNoteSearchState(editor);
}

export function getNoteSearchState(editor) {
  const state = editor && !editor.isDestroyed
    ? searchPluginKey.getState(editor.state)
    : null;
  return {
    query: state?.query || '',
    ranges: state?.ranges || [],
    activeIndex: Number.isInteger(state?.activeIndex) ? state.activeIndex : -1,
  };
}
