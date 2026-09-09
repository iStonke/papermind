const LEGACY_COLLECTION_PINK = '#db2777';
export const COLLECTION_RED = '#dc2626';

export function normalizeCollectionColor(color) {
  if (!color) return null;
  return String(color).toLowerCase() === LEGACY_COLLECTION_PINK ? COLLECTION_RED : color;
}

// Notebook-local legacy colors are deliberately ignored.
export function noteCollectionColor(item, collections) {
  const color = collections.find(collection => collection.id === item?.collection_id)?.color;
  return normalizeCollectionColor(color);
}
