// Notebook-local legacy colors are deliberately ignored.
export function noteCollectionColor(item, collections) {
  return collections.find(collection => collection.id === item?.collection_id)?.color || null;
}
