export const NOTE_PAGE_LAYOUT_COLUMNS = Object.freeze([1, 2, 3, 4, 5]);

const EMPTY_PARAGRAPH = Object.freeze({ type: 'paragraph' });

export function normalizeNotePageLayoutColumns(value, fallback = 2) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(5, Math.max(1, Math.round(parsed)));
}

function isEmptyParagraph(node) {
  return node?.type === 'paragraph' && (!Array.isArray(node.content) || node.content.length === 0);
}

function normalizedColumnContent(content) {
  return Array.isArray(content) && content.length ? content : [{ ...EMPTY_PARAGRAPH }];
}

function mergeableColumnContent(content) {
  const normalized = normalizedColumnContent(content);
  return normalized.length === 1 && isEmptyParagraph(normalized[0]) ? [] : normalized;
}

function layoutColumns(layout) {
  if (layout?.type !== 'pageLayout' || !Array.isArray(layout.content)) return [];
  return layout.content
    .filter((column) => column?.type === 'layoutColumn')
    .map((column) => normalizedColumnContent(column.content));
}

export function notePageLayoutColumnCount(layout) {
  const count = layoutColumns(layout).length;
  return count >= 1 ? normalizeNotePageLayoutColumns(count) : null;
}

export function createNotePageLayout(requestedColumns = 2) {
  const columns = normalizeNotePageLayoutColumns(requestedColumns);
  return {
    type: 'pageLayout',
    attrs: { columns },
    content: Array.from({ length: columns }, () => ({
      type: 'layoutColumn',
      content: [{ ...EMPTY_PARAGRAPH }],
    })),
  };
}

/** Ändert ausschließlich den gewählten Layoutblock und bewahrt seine Inhalte. */
export function resizeNotePageLayout(layout, requestedColumns) {
  const columns = normalizeNotePageLayoutColumns(requestedColumns);
  const existingColumns = layoutColumns(layout);
  if (!existingColumns.length) return createNotePageLayout(columns);

  const nextColumns = existingColumns.slice(0, columns);
  if (existingColumns.length > columns) {
    const overflow = existingColumns.slice(columns).flatMap(mergeableColumnContent);
    const lastIndex = columns - 1;
    nextColumns[lastIndex] = [
      ...mergeableColumnContent(nextColumns[lastIndex]),
      ...overflow,
    ];
  }
  while (nextColumns.length < columns) nextColumns.push([{ ...EMPTY_PARAGRAPH }]);

  return {
    ...layout,
    attrs: { ...(layout.attrs || {}), columns },
    content: nextColumns.map((content) => ({
      type: 'layoutColumn',
      content: normalizedColumnContent(content),
    })),
  };
}

/** Löst einen Layoutblock in normale Blöcke in visueller Lesereihenfolge auf. */
export function flattenNotePageLayout(layout) {
  const content = layoutColumns(layout).flatMap(mergeableColumnContent);
  return content.length ? content : [{ ...EMPTY_PARAGRAPH }];
}
