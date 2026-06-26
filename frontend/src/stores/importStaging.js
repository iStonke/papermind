import { defineStore } from 'pinia';

function makeId(prefix) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sanitizeTitle(title, fallback = 'Neues Dokument') {
  const normalized = String(title || '').replace(/\s+/g, ' ').trim();
  return normalized || fallback;
}

function normalizeTagId(tagId) {
  return String(tagId || '').trim();
}

function normalizeTagIds(tagIds = []) {
  const seen = new Set();
  const normalized = [];
  for (const tagId of tagIds) {
    const value = normalizeTagId(tagId);
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    normalized.push(value);
  }
  return normalized;
}

function createDocument({ title, sourceType = 'manual', pages = [], collapsed = false, tags = [] } = {}) {
  const id = makeId('staging-doc');
  const normalizedPages = pages.map((page) => ({
    ...page,
    id: page.id || makeId('staging-page'),
    docId: id,
    rotation: normalizeRotation(page.rotation),
    colorMode: normalizeColorMode(page.colorMode),
    deleted: Boolean(page.deleted)
  }));
  return {
    id,
    title: sanitizeTitle(title),
    sourceType,
    pages: normalizedPages,
    tags: normalizeTagIds(tags),
    meta: {
      isScanSession: false,
      scanSourceFileIds: [],
      titleSuggestion: '',
      titleSuggestionStatus: 'idle',
      titleSuggestionUsedFallback: false,
      titleSuggestionPollExhausted: false,
      titleSuggestionMeta: null
    },
    collapsed
  };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function normalizeRotation(value) {
  const normalized = Number(value) || 0;
  if (normalized === 90 || normalized === 180 || normalized === 270) {
    return normalized;
  }
  return 0;
}

const PAGE_COLOR_MODES = ['color', 'grayscale', 'bw'];

function normalizeColorMode(value) {
  return PAGE_COLOR_MODES.includes(value) ? value : 'color';
}

function buildPagesForSource(docId, sourceFileId, pageCount, thumbUrls = []) {
  const normalizedPageCount = Math.max(0, Number(pageCount || 0));
  return Array.from({ length: normalizedPageCount }, (_, pageIndex) => ({
    id: makeId('staging-page'),
    docId,
    sourceFileId,
    pageIndex,
    rotation: 0,
    colorMode: 'color',
    thumbUrl: String(thumbUrls[pageIndex] || ''),
    deleted: false
  }));
}

export const useImportStagingStore = defineStore('importStaging', {
  state: () => ({
    batchId: '',
    createdAt: 0,
    documents: [],
    stagingFiles: new Map(),
    sourceMetaById: new Map()
  }),

  getters: {
    documentCount: (state) => state.documents.length,
    totalPages: (state) => state.documents.reduce((sum, doc) => sum + doc.pages.length, 0),
    emptyDocuments: (state) => state.documents.filter((doc) => doc.pages.length === 0),
    hasEmptyDocuments() {
      return this.emptyDocuments.length > 0;
    },
    isImportDisabled() {
      return this.documentCount === 0 || this.hasEmptyDocuments;
    },
    importableDocuments: (state) => state.documents.filter((doc) => doc.pages.length > 0),
    commitDocuments() {
      return this.importableDocuments.map((doc) => ({
        title: sanitizeTitle(doc.title),
        tag_ids: normalizeTagIds(doc.tags),
        pages: doc.pages.map((page) => ({
          source_file_id: page.sourceFileId,
          page_index: Number(page.pageIndex),
          rotation: normalizeRotation(page.rotation)
        }))
      }));
    }
  },

  actions: {
    collectUsedSourceFileIds() {
      const ids = new Set();
      for (const document of this.documents) {
        for (const page of document.pages || []) {
          const sourceFileId = String(page?.sourceFileId || '').trim();
          if (sourceFileId) {
            ids.add(sourceFileId);
          }
        }
      }
      return ids;
    },

    cleanupUnusedSources() {
      const usedSourceIds = this.collectUsedSourceFileIds();
      for (const sourceFileId of this.stagingFiles.keys()) {
        if (!usedSourceIds.has(sourceFileId)) {
          this.stagingFiles.delete(sourceFileId);
        }
      }
      for (const sourceFileId of this.sourceMetaById.keys()) {
        if (!usedSourceIds.has(sourceFileId)) {
          this.sourceMetaById.delete(sourceFileId);
        }
      }
    },

    pruneDocumentIfEmpty(documentId) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      if (document.pages.length > 0) {
        return;
      }
      this.deleteDocument(documentId);
    },

    ensureBatch() {
      if (this.batchId) {
        return;
      }
      this.batchId = makeId('batch');
      this.createdAt = Date.now();
    },

    reset() {
      this.batchId = '';
      this.createdAt = 0;
      this.documents = [];
      this.stagingFiles = new Map();
      this.sourceMetaById = new Map();
    },

    setStagingFile(sourceFileId, file, meta = {}) {
      this.stagingFiles.set(sourceFileId, file);
      this.sourceMetaById.set(sourceFileId, {
        sourceFileId,
        originalName: String(meta.originalName || file?.name || '').trim(),
        pageCount: Number(meta.pageCount || 0),
        isImportInbox: Boolean(meta.isImportInbox)
      });
    },

    addDocumentFromSource({ sourceFileId, title, pageCount, thumbUrls = [], insertIndex = null, tags = [] }) {
      this.ensureBatch();
      // docId leer: createDocument weist den korrekten Wert beim Anlegen zu.
      const pages = buildPagesForSource('', sourceFileId, pageCount, thumbUrls);

      const created = createDocument({
        title,
        sourceType: 'pdf',
        tags,
        pages,
        collapsed: false
      });

      if (insertIndex == null) {
        this.documents.push(created);
      } else {
        const targetIndex = clamp(Number(insertIndex) || 0, 0, this.documents.length);
        this.documents.splice(targetIndex, 0, created);
      }
      return created;
    },

    appendSourceToDocument(documentId, { sourceFileId, pageCount, thumbUrls = [] }) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      const pages = buildPagesForSource(document.id, sourceFileId, pageCount, thumbUrls);
      if (pages.length === 0) {
        return;
      }
      document.pages.push(...pages);
      if (document.sourceType !== 'manual' && document.pages.length > pages.length) {
        document.sourceType = 'manual';
      }
    },

    addEmptyDocument(insertIndex = this.documents.length, title = 'Neues Dokument', tags = []) {
      this.ensureBatch();
      const document = createDocument({
        title,
        sourceType: 'manual',
        tags,
        pages: [],
        collapsed: false
      });
      const targetIndex = clamp(Number(insertIndex) || 0, 0, this.documents.length);
      this.documents.splice(targetIndex, 0, document);
      return document;
    },

    deleteDocument(documentId) {
      const docIndex = this.documents.findIndex((entry) => entry.id === documentId);
      if (docIndex < 0) {
        return;
      }
      this.documents.splice(docIndex, 1);
      if (this.documents.length === 0) {
        this.reset();
        return;
      }
      this.cleanupUnusedSources();
    },

    renameDocument(documentId, nextTitle) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      document.title = sanitizeTitle(nextTitle, 'Neues Dokument');
    },

    setDocumentTags(documentId, tagIds = []) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      document.tags = normalizeTagIds(tagIds);
    },

    addDocumentTag(documentId, tagId) {
      const value = normalizeTagId(tagId);
      if (!value) {
        return;
      }
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      if (!Array.isArray(document.tags)) {
        document.tags = [];
      }
      if (!document.tags.includes(value)) {
        document.tags.push(value);
      }
    },

    removeDocumentTag(documentId, tagId) {
      const value = normalizeTagId(tagId);
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document || !value) {
        return;
      }
      document.tags = (document.tags || []).filter((entry) => entry !== value);
    },

    setDocumentTitleDraft(documentId, nextTitle) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      document.title = String(nextTitle || '');
    },

    toggleDocumentCollapsed(documentId) {
      const document = this.documents.find((entry) => entry.id === documentId);
      if (!document) {
        return;
      }
      document.collapsed = !document.collapsed;
    },

    moveDocument(documentId, targetIndex) {
      const fromIndex = this.documents.findIndex((entry) => entry.id === documentId);
      if (fromIndex < 0) {
        return;
      }
      const clampedTarget = clamp(Number(targetIndex) || 0, 0, this.documents.length);
      const [document] = this.documents.splice(fromIndex, 1);
      let insertionIndex = clampedTarget;
      if (fromIndex < clampedTarget) {
        insertionIndex -= 1;
      }
      insertionIndex = clamp(insertionIndex, 0, this.documents.length);
      this.documents.splice(insertionIndex, 0, document);
    },

    rotatePage(pageId, direction = 'right') {
      const location = this.findPageLocation(pageId);
      if (!location) {
        return;
      }
      const delta = direction === 'left' ? -90 : 90;
      const nextRotation = (location.page.rotation + delta + 360) % 360;
      location.page.rotation = normalizeRotation(nextRotation);
    },

    setPageColorMode(pageId, colorMode) {
      const location = this.findPageLocation(pageId);
      if (!location) {
        return;
      }
      location.page.colorMode = normalizeColorMode(colorMode);
    },

    removePage(pageId) {
      const location = this.findPageLocation(pageId);
      if (!location) {
        return;
      }
      const sourceDocId = this.documents[location.docIndex].id;
      this.documents[location.docIndex].pages.splice(location.pageIndex, 1);
      this.pruneDocumentIfEmpty(sourceDocId);
      this.cleanupUnusedSources();
    },

    remapSourcePagesAfterRemoval(sourceFileId, removedPageIndices = [], nextPageCount = null) {
      const normalizedId = String(sourceFileId || '').trim();
      const removed = Array.from(new Set((removedPageIndices || [])
        .map((index) => Number(index))
        .filter((index) => Number.isInteger(index) && index >= 0)))
        .sort((a, b) => a - b);
      if (!normalizedId || removed.length === 0) {
        return;
      }

      for (const document of this.documents) {
        for (const page of document.pages || []) {
          if (String(page?.sourceFileId || '').trim() !== normalizedId) {
            continue;
          }
          const currentIndex = Number(page.pageIndex || 0);
          const shift = removed.filter((removedIndex) => removedIndex < currentIndex).length;
          page.pageIndex = Math.max(0, currentIndex - shift);
        }
      }

      const meta = this.sourceMetaById.get(normalizedId);
      if (meta) {
        const fallbackCount = Math.max(0, Number(meta.pageCount || 0) - removed.length);
        const normalizedNextPageCount = Number(nextPageCount);
        meta.pageCount = nextPageCount != null && Number.isInteger(normalizedNextPageCount)
          ? Math.max(0, normalizedNextPageCount)
          : fallbackCount;
        this.sourceMetaById.set(normalizedId, meta);
      }
    },

    updateSourceThumbnails(sourceFileId, thumbUrls = []) {
      const normalizedId = String(sourceFileId || '').trim();
      if (!normalizedId) {
        return;
      }
      for (const document of this.documents) {
        for (const page of document.pages || []) {
          if (String(page?.sourceFileId || '').trim() !== normalizedId) {
            continue;
          }
          page.thumbUrl = String(thumbUrls[Number(page.pageIndex || 0)] || page.thumbUrl || '');
        }
      }
    },

    removeSourceFile(sourceFileId) {
      const normalizedId = String(sourceFileId || '').trim();
      if (!normalizedId) {
        return;
      }

      for (let docIndex = this.documents.length - 1; docIndex >= 0; docIndex -= 1) {
        const document = this.documents[docIndex];
        document.pages = (document.pages || []).filter(
          (page) => String(page?.sourceFileId || '').trim() !== normalizedId
        );
        if (document.pages.length === 0) {
          this.documents.splice(docIndex, 1);
        }
      }

      this.stagingFiles.delete(normalizedId);
      this.sourceMetaById.delete(normalizedId);

      if (this.documents.length === 0) {
        this.reset();
        return;
      }
      this.cleanupUnusedSources();
    },

    movePage(pageId, targetDocId, targetPageIndex = null) {
      const source = this.findPageLocation(pageId);
      if (!source) {
        return;
      }
      const sourceDocId = this.documents[source.docIndex]?.id || null;
      const targetDocIndex = this.documents.findIndex((doc) => doc.id === targetDocId);
      if (targetDocIndex < 0) {
        return;
      }

      const [page] = this.documents[source.docIndex].pages.splice(source.pageIndex, 1);
      if (!page) {
        return;
      }

      const targetDoc = this.documents[targetDocIndex];
      let insertionIndex = targetPageIndex == null ? targetDoc.pages.length : Number(targetPageIndex);
      if (Number.isNaN(insertionIndex)) {
        insertionIndex = targetDoc.pages.length;
      }

      if (source.docIndex === targetDocIndex && source.pageIndex < insertionIndex) {
        insertionIndex -= 1;
      }

      insertionIndex = clamp(insertionIndex, 0, targetDoc.pages.length);
      page.docId = targetDoc.id;
      targetDoc.pages.splice(insertionIndex, 0, page);
      if (source.docIndex !== targetDocIndex && sourceDocId) {
        this.pruneDocumentIfEmpty(sourceDocId);
      }
    },

    movePageToNewDocument(pageId, insertIndex, title = 'Neues Dokument') {
      const source = this.findPageLocation(pageId);
      if (!source) {
        return null;
      }
      const sourceDocId = this.documents[source.docIndex]?.id || null;
      const [page] = this.documents[source.docIndex].pages.splice(source.pageIndex, 1);
      if (!page) {
        return null;
      }

      const sourceDocument = this.documents[source.docIndex];
      const created = createDocument({
        title,
        sourceType: 'manual',
        tags: sourceDocument?.tags || [],
        pages: [
          {
            ...page,
            id: makeId('staging-page')
          }
        ],
        collapsed: false
      });

      const targetIndex = clamp(Number(insertIndex) || 0, 0, this.documents.length);
      this.documents.splice(targetIndex, 0, created);
      if (sourceDocId) {
        this.pruneDocumentIfEmpty(sourceDocId);
      }
      return created;
    },

    splitPageToNewDocument(pageId) {
      const source = this.findPageLocation(pageId);
      if (!source) {
        return null;
      }
      const sourceDocument = this.documents[source.docIndex];
      const title = `Auszug - ${sanitizeTitle(sourceDocument.title, 'Dokument')}`;
      return this.movePageToNewDocument(pageId, source.docIndex + 1, title);
    },

    findPageLocation(pageId) {
      for (let docIndex = 0; docIndex < this.documents.length; docIndex += 1) {
        const pageIndex = this.documents[docIndex].pages.findIndex((page) => page.id === pageId);
        if (pageIndex >= 0) {
          return {
            docIndex,
            pageIndex,
            page: this.documents[docIndex].pages[pageIndex]
          };
        }
      }
      return null;
    }
  }
});
