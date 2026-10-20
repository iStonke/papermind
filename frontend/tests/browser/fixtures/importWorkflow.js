import { createApp, h, nextTick, ref } from 'vue';
import { createPinia } from 'pinia';
import { VApp } from 'vuetify/components';
import vuetify from '../../../src/plugins/vuetify.js';
import { resetApiSession } from '../../../src/api/session.js';
import { useImportStagingStore } from '../../../src/stores/importStaging.js';
import { useCategoryStore } from '../../../src/stores/categories.js';
import { useCorrespondentStore } from '../../../src/stores/correspondents.js';
import { documentRevision } from '../../../src/utils/importWorkflow.js';
import ImportStagingDialog from '../../../src/components/ImportStagingDialog.vue';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export async function mountImportWorkflow({ documents = 1, pages = 3, title = 'Arbeitsstätte', owner = 'import-browser-test', restore = false, thumbnails = true } = {}) {
  resetApiSession(owner);
  const pinia = createPinia();
  const store = useImportStagingStore(pinia);
  useCategoryStore(pinia).categories = [{ id: 'brief', name: 'Brief' }];
  const correspondents = useCorrespondentStore(pinia);
  correspondents.isLoaded = true;
  if (!restore) for (let index = 0; index < documents; index++) {
    const sourceId = `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
    const doc = store.addDocumentFromSource({ sourceFileId: sourceId, title: index ? `Dokument ${index + 1}` : title, pageCount: pages,
      thumbUrls: thumbnails ? Array(pages).fill('data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="280"><rect width="200" height="280" fill="white"/><text x="20" y="60">Dokumentvorschau</text></svg>')) : [] });
    store.setStagingFile(sourceId, null, { pageCount: pages, sourceRevision: 'revision-1', originalName: `${doc.title}.pdf` });
    doc.meta.titleSuggestionStatus = 'ready';
    doc.meta.analysisRevision = documentRevision(doc, store.sourceMetaById);
  }
  const open = ref(true);
  const scannerActive = ref(false);
  const scanner = ref({ id: 'scanner-fixture', name: 'Testscanner', live_page_mode: false });
  const scannerJobs = ref([]);
  const component = ref(null);
  const committed = [];
  const commands = [];
  createApp({ render: () => h(VApp, null, { default: () => h(ImportStagingDialog, {
    ref: component, modelValue: open.value, 'onUpdate:modelValue': value => { open.value = value; },
    scannerActive: scannerActive.value, scannerJobs: scannerJobs.value,
    scanner: scanner.value,
    onCommitted: value => committed.push(value), onScan: value => commands.push(value),
  }) }) }).use(pinia).use(vuetify).mount('#app');
  window.importFixture = { store, correspondents, open, scannerActive, scanner, scannerJobs, component, committed, commands,
    setTheme: name => vuetify.theme.change(name) };
  await nextTick();
}
