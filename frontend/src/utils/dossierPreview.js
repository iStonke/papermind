export function isPdfDossierItem(item) {
  if (item?.item_type !== 'document' || !item.document_id) return false;
  const filename = String(item.document?.original_filename || '').trim();
  return !filename || /\.pdf$/i.test(filename);
}
