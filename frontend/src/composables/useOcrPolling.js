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
 * @param {Function}              options.fetchDocuments      – Lädt Dokumente neu
 */
export function useOcrPolling({
  documents,
  hasActiveOcrJob,
  isLoadingDocuments,
  selectedDocumentId,
  fetchDocuments
}) {
  let statusPollTimer = null;

  async function pollOcrStatus() {
    if (isLoadingDocuments.value) {
      return;
    }
    const listHasProcessing = documents.value.some((doc) => doc.status === 'processing');
    if (!listHasProcessing && !hasActiveOcrJob.value) {
      return;
    }
    try {
      // Stiller Refresh: Liste im Hintergrund aktualisieren ohne Lade-Skeleton /
      // Settle-Animation, damit die UI während der Analyse nicht flackert.
      await fetchDocuments(selectedDocumentId.value, { silent: true });
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
