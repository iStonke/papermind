import { toValue } from 'vue';
import { apiFetch } from '../api/client.js';
import { mapApiError } from '../stores/notifications';
import { ensureImportForm, sourcePages } from '../utils/importWorkflow.js';
import { parseDocumentDateInput } from '../utils/dates.js';

// Owns the durable request/receipt transaction. UI selection and focus stay in
// the dialog; retries always reuse the exact persisted idempotency request.
export function useImportCommit({ store, correspondents, settings, retentionEnabled, autoEmbed,
  persistence, notify, diagnostics, onCreated, onEmpty, onSelectionCleared }) {
  async function run(entries) {
    try {
      if (!store.pendingCommit) {
        await correspondents.ensureLoaded();
        const submitted = {}, bodyDocuments = [];
        const selectedIds = new Set(entries.flatMap(entry => entry.pages.map(page => page.id)));
        const remainingSources = new Set(store.documents.flatMap(doc => doc.pages.filter(page => !selectedIds.has(page.id)).map(page => page.sourceFileId)));
        for (const { document: doc, pages } of entries) {
          const form = ensureImportForm(doc);
          const raw = typeof form.correspondentId === 'object' && form.correspondentId
            ? form.correspondentId.value || form.correspondentId.id || form.correspondentId.name || form.correspondentId.title : form.correspondentId;
          const correspondent = raw ? correspondents.findById(raw) || correspondents.findByName(raw) : null;
          if (raw && !correspondent) throw new Error('Bitte einen vorhandenen Korrespondenten wählen.');
          submitted[doc.id] = pages.map(page => page.id);
          bodyDocuments.push({ client_document_id: doc.id, title: doc.title.trim(),
            manual_fields: Object.entries(form.touched).filter(([, touched]) => touched).map(([field]) => field),
            tag_ids: doc.tags || [], tag_names: doc.meta?.pendingTagNames || [], pages: sourcePages({ ...doc, pages }, store.sourceMetaById),
            document_type: form.category || null, correspondent_id: correspondent?.id || null,
            note: String(form.note || '').trim() || null, date: parseDocumentDateInput(form.date).iso,
            retention: toValue(retentionEnabled) && form.retention ? {
              status: form.retention.status || 'manual', period_years: form.retention.period_years ?? null,
              paper_original: form.retention.paper_original || 'unclear', reason: form.retention.reason || null,
            } : null,
          });
        }
        for (const doc of store.availableDraft?.documents || []) for (const page of doc.pages) remainingSources.add(page.sourceFileId);
        store.pendingCommit = { body: { request_id: crypto.randomUUID(), documents: bodyDocuments, preserve_source_ids: [...remainingSources],
          options: { auto_ocr: Boolean(settings.settings.documents.auto_ocr),
            auto_index: Boolean(settings.settings.documents.auto_tagging && settings.settings.documents.auto_ocr), auto_embed: Boolean(toValue(autoEmbed)) } }, submitted };
      }
      const attempt = store.pendingCommit;
      if (!await persistence.save() || persistence.conflict.value) return;
      diagnostics.start('commit', 'commit_start');
      const payload = await apiFetch('/api/import/commit', { method: 'POST', body: JSON.stringify(attempt.body), timeoutMs: 180000 });
      diagnostics.end('commit', 'commit_complete', { pages: Object.values(attempt.submitted).flat().length });
      const created = payload.created || [], errors = payload.errors || [];
      for (const warning of created.flatMap(item => item.warnings || [])) notify({ type: 'warning', message: warning });
      const completedPageIds = created.flatMap(item => attempt.submitted[item.client_document_id] || []);
      if (created.length) {
        const completed = new Set(completedPageIds);
        const remaining = new Set(store.documents.flatMap(doc => doc.pages.filter(page => !completed.has(page.id)).map(page => page.sourceFileId)));
        const createdIds = new Set(created.map(item => item.client_document_id));
        const completedSources = [...new Set(attempt.body.documents.filter(doc => createdIds.has(doc.client_document_id)).flatMap(doc => doc.pages.map(page => page.source_file_id)))].filter(id => !remaining.has(id));
        onCreated({ ...payload, remaining: store.totalPages > completedPageIds.length, completed_source_ids: completedSources });
        if (!errors.length && !remaining.size) onEmpty();
        store.completePages(completedPageIds);
        onSelectionCleared();
      }
      for (const error of errors) { const doc = store.documents.find(doc => doc.id === error.client_document_id); if (doc) doc.meta.commitError = error; }
      store.pendingCommit = null;
      await persistence.save();
      if (!errors.length && !store.totalPages) {
        notify({ type: 'success', message: created.some(item => item.processing_queued) ? 'Import gespeichert. Die Texterkennung läuft im Hintergrund.' : 'Import gespeichert.' });
        onEmpty();
      } else if (errors.length) notify({ type: 'warning', message: `${created.length ? `${created.length} Dokumente gespeichert. ` : ''}${errors[0].message}` });
      else notify({ type: 'success', message: 'Auswahl importiert. Übrige Seiten bleiben im Entwurf.' });
    } catch (error) {
      if ([400, 403, 409, 413, 422].includes(error.status)) store.pendingCommit = null;
      notify({ type: 'error', message: mapApiError(error, 'Importstatus konnte nicht bestätigt werden. Bitte erneut prüfen; alle Seiten bleiben erhalten.') });
    }
  }
  return { run };
}
