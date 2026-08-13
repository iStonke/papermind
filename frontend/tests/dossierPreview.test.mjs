import assert from 'node:assert/strict';
import test from 'node:test';

import { isPdfDossierItem } from '../src/utils/dossierPreview.js';

const pdfItem = {
  id: 'pdf-1',
  item_type: 'document',
  document_id: 'document-1',
  document: { original_filename: 'Akte.PDF' },
};

test('PDF preview recognizes PDF document items', () => {
  const nonPdf = {
    id: 'image-1',
    item_type: 'document',
    document_id: 'document-2',
    document: { original_filename: 'scan.png' },
  };

  assert.equal(isPdfDossierItem(pdfItem), true);
  assert.equal(isPdfDossierItem(nonPdf), false);
  assert.equal(isPdfDossierItem({ id: 'note-1', item_type: 'note' }), false);
});
