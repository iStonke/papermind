import { buildDocumentMetadataPatch } from '../../utils/documentMetadata.js';
import { notifyError, logDevError } from '../../stores/notifications.js';

export function createMetadataAutosave({ state, actions, apiBaseUrl }) {
  const { selectedDocumentDetail, isSavingMetadata, isMetadataDirty, metadataDraftRevision, metadataDocName, metadataDocDate, metadataNotes, metadataDocDateHasError, metadataSuccessMessage, metadataErrorMessage, documents, selectedDocumentId, documentListQuery, isRetentionFeatureEnabled } = state;
  const { getDocumentNameDraft, parseResponseError, applyKnownFavoriteState, applyMetadataFromDetail, fetchDocumentDetail, fetchDocuments, loadRetention } = actions;
  let metadataAutosaveDebounceTimer = null;
  let shouldRunMetadataAutosaveAfterSave = false;
  let disposed = false;
  const METADATA_AUTOSAVE_DEBOUNCE_MS = 900;
  function scheduleMetadataAutosave() {
    if (disposed) return;
    if (metadataAutosaveDebounceTimer) {
      window.clearTimeout(metadataAutosaveDebounceTimer);
    }
    metadataAutosaveDebounceTimer = window.setTimeout(() => {
      metadataAutosaveDebounceTimer = null;
      if (!selectedDocumentDetail.value || !isMetadataDirty.value) {
        return;
      }
      if (isSavingMetadata.value) {
        shouldRunMetadataAutosaveAfterSave = true;
        return;
      }
      void saveMetadata({ skipDocumentReload: true, silentSuccess: true });
    }, METADATA_AUTOSAVE_DEBOUNCE_MS);
  }

  function commitMetadataTextFields() {
    if (metadataAutosaveDebounceTimer) {
      window.clearTimeout(metadataAutosaveDebounceTimer);
      metadataAutosaveDebounceTimer = null;
    }
    if (!selectedDocumentDetail.value || !isMetadataDirty.value) {
      return;
    }
    if (isSavingMetadata.value) {
      shouldRunMetadataAutosaveAfterSave = true;
      return;
    }
    void saveMetadata({ skipDocumentReload: true, silentSuccess: true });
  }

  async function saveMetadata(options = {}) {
    if (disposed) return;
    const skipDocumentReload = options.skipDocumentReload === true;
    const silentSuccess = options.silentSuccess === true;
    if (!selectedDocumentDetail.value) {
      return;
    }
    if (isSavingMetadata.value) {
      shouldRunMetadataAutosaveAfterSave = true;
      return;
    }
    if (!isMetadataDirty.value) {
      return;
    }

    const documentId = selectedDocumentDetail.value.id;
    const detailSnapshot = selectedDocumentDetail.value;
    const saveRevision = metadataDraftRevision.value;
    const metadataPatch = buildDocumentMetadataPatch({
      detail: detailSnapshot,
      currentNameDraft: getDocumentNameDraft(detailSnapshot),
      draftName: metadataDocName.value,
      draftDate: metadataDocDate.value,
      draftNotes: metadataNotes.value
    });
    metadataDocDateHasError.value = !metadataPatch.parsedDocumentDate.ok;
    if (!metadataPatch.hasChanges) {
      return;
    }

    metadataSuccessMessage.value = '';
    metadataErrorMessage.value = '';
    isSavingMetadata.value = true;
    const { patchBody, parsedDocumentDate, dateChanged } = metadataPatch;

    try {
      if (parsedDocumentDate.ok && metadataDraftRevision.value === saveRevision) {
        metadataDocDate.value = parsedDocumentDate.display;
      }

      const patchResponse = await fetch(`${apiBaseUrl}/api/documents/${documentId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patchBody),
        keepalive: true
      });

      if (!patchResponse.ok) {
        throw new Error(await parseResponseError(patchResponse));
      }

      let updatedDetail = null;
      try {
        updatedDetail = applyKnownFavoriteState(await patchResponse.json());
      } catch (error) {
        logDevError(error, 'json-parse');
        updatedDetail = null;
      }

      if (updatedDetail?.id) {
        const listIndex = documents.value.findIndex((document) => document.id === updatedDetail.id);
        if (listIndex >= 0) {
          const existing = documents.value[listIndex];
          documents.value.splice(listIndex, 1, {
            ...existing,
            ...updatedDetail
          });
        }
        if (selectedDocumentId.value === documentId) {
          selectedDocumentDetail.value = updatedDetail;
        }
        if (
          selectedDocumentId.value === documentId
          && metadataDraftRevision.value === saveRevision
          && parsedDocumentDate.ok
        ) {
          applyMetadataFromDetail(updatedDetail);
        }
      } else {
        const localPatch = { ...patchBody };
        if (dateChanged) {
          localPatch.document_date_source = 'manual';
          localPatch.document_date_confidence = null;
          localPatch.document_date_candidates = null;
        }
        if (selectedDocumentDetail.value?.id === documentId) {
          selectedDocumentDetail.value = {
            ...selectedDocumentDetail.value,
            ...localPatch
          };
        }
        const listIndex = documents.value.findIndex((document) => document.id === documentId);
        if (listIndex >= 0) {
          const existing = documents.value[listIndex];
          documents.value.splice(listIndex, 1, {
            ...existing,
            ...localPatch
          });
        }
        if (selectedDocumentDetail.value?.id === documentId) {
          if (metadataDraftRevision.value === saveRevision && parsedDocumentDate.ok) {
            applyMetadataFromDetail(selectedDocumentDetail.value);
          }
        }
        if (!skipDocumentReload) {
          await fetchDocumentDetail(documentId);
        }
      }

      const listDependsOnPatch = (
        dateChanged
        || (!skipDocumentReload)
        || (Object.prototype.hasOwnProperty.call(patchBody, 'display_name') && (
          documentListQuery.sort === 'name' || Boolean(documentListQuery.q)
        ))
        || (Object.prototype.hasOwnProperty.call(patchBody, 'notes') && Boolean(documentListQuery.q))
        || documentListQuery.sort === 'updated_at'
      );
      if (listDependsOnPatch) {
        await fetchDocuments(documentId, {
          autoSelectFirst: false,
          allowPreferredOutsideList: true,
          silent: true
        });
      }
      if (dateChanged && selectedDocumentId.value === documentId && isRetentionFeatureEnabled.value) {
        await loadRetention(documentId, { force: true });
      }
      if (!silentSuccess) {
        metadataSuccessMessage.value = 'Metadaten gespeichert.';
      }
    } catch (error) {
      metadataErrorMessage.value = notifyError(error, 'Speichern fehlgeschlagen.');
    } finally {
      isSavingMetadata.value = false;
      const hadQueuedSave = shouldRunMetadataAutosaveAfterSave;
      const hasNewerDraft = metadataDraftRevision.value !== saveRevision;
      shouldRunMetadataAutosaveAfterSave = false;
      if (
        selectedDocumentId.value === documentId
        && (hadQueuedSave || hasNewerDraft)
        && isMetadataDirty.value
      ) {
        scheduleMetadataAutosave();
      }
    }
  }

  function dispose() {
    disposed = true;
    if (metadataAutosaveDebounceTimer) window.clearTimeout(metadataAutosaveDebounceTimer);
  }
  return { saveMetadata, scheduleMetadataAutosave, commitMetadataTextFields, dispose };
}
