import { onMounted, onBeforeUnmount } from 'vue';
import { logDevError } from '../stores/notifications';

const STATUS_POLL_INTERVAL_MS = 5000;

/**
 * Startet einen regelmäßigen Polling-Zyklus der Dokumentenliste,
 * solange Dokumente mit Status 'processing' vorhanden sind oder ein
 * aktiver OCR-Job läuft. Lifecycle-Hooks werden intern verwaltet.
 *
 * @param {Object} options
 * @param {import('vue').Ref}     options.documents           – Dokumentenliste aus dem Store
 * @param {import('vue').Ref}     options.hasActiveOcrJob     – Ob der ausgewählte Doc einen laufenden Job hat
 * @param {import('vue').Ref}     options.isLoadingDocuments  – Ladeindikator (kein Poll bei laufendem Fetch)
 * @param {import('vue').Ref}     options.selectedDocumentId  – Aktuell ausgewählte Doc-ID
 * @param {Function}              options.refreshDocumentStatuses – Lädt nur Statusfelder der aktiven Dokumente
 */
export function useOcrPolling({
  documents,
  hasActiveOcrJob,
  isLoadingDocuments,
  selectedDocumentId,
  refreshDocumentStatuses
}) {
  let statusPollTimer = null;

  async function pollOcrStatus() {
    if (isLoadingDocuments.value) {
      return;
    }
    const processingIds = documents.value
      .filter((doc) => doc.status === 'processing' || ['queued', 'running'].includes(doc.ocr_status))
      .map((doc) => doc.id)
      .filter(Boolean);
    if (hasActiveOcrJob.value && selectedDocumentId.value) {
      processingIds.push(selectedDocumentId.value);
    }
    const uniqueIds = [...new Set(processingIds)].slice(0, 100);
    if (uniqueIds.length === 0) {
      return;
    }
    try {
      await refreshDocumentStatuses(uniqueIds);
    } catch (error) {
      logDevError(error, 'ocr-polling');
    }
  }

  onMounted(() => {
    statusPollTimer = window.setInterval(() => {
      void pollOcrStatus();
    }, STATUS_POLL_INTERVAL_MS);
  });

  onBeforeUnmount(() => {
    if (statusPollTimer) {
      window.clearInterval(statusPollTimer);
    }
  });
}
