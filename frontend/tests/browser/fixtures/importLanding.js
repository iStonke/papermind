import { createApp, h, nextTick, ref } from 'vue';
import { createPinia } from 'pinia';
import { useAuthStore } from '../../../src/stores/auth.js';
import { useDocumentStore } from '../../../src/stores/documents.js';
import DocumentListPanel from '../../../src/components/DocumentListPanel.vue';
import DocumentTimeline from '../../../src/components/DocumentTimeline.vue';
import DocumentGroupedList from '../../../src/components/DocumentGroupedList.vue';
import ImportFlightCard from '../../../src/components/ImportFlightCard.vue';
import SidebarItem from '../../../src/components/SidebarItem.vue';
import { resolveImportDestination } from '../../../src/utils/importLanding.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
import '../../../src/theme/lists.css';
import '../../../src/workspaces/documents/workspace.css';

export function mountImportLanding(mode, documents) {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'import-test', username: 'test' };
  useDocumentStore(pinia).documents = documents;
  const panel = ref(null);
  const sidebar = ref(null);
  const flight = ref(null);
  const refreshKey = ref(0);
  const component = mode === 'list' ? DocumentListPanel : mode === 'timeline' ? DocumentTimeline : DocumentGroupedList;
  const app = createApp({ render: () => h('div', { style: 'height:430px;width:540px;display:flex' }, [
    h(component, { ref: panel, class: 'panel-middle__view', style: 'flex:1;min-height:0', documents, grouping: mode, queryPath: '/api/documents', refreshKey: refreshKey.value }),
    h('div', { class: 'panel-left', style: 'position:absolute;left:560px;top:30px;width:200px' }, [
      h(SidebarItem, { ref: sidebar }, { default: () => 'Alle Dokumente', icon: () => h('span', { style: 'display:block;width:24px;height:24px' }, '▤') }),
    ]),
    flight.value ? h(ImportFlightCard, {
      ...flight.value,
      onApproaching: () => { if (window.importDestination === 'list') panel.value.maskLandingThumb(); },
      onLanded: () => {
        const rect = document.querySelector('.import-flight-card').getBoundingClientRect();
        window.lastLanding = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
        if (window.importDestination === 'list') {
          panel.value.revealImportLanding();
          panel.value.resolveImportLanding(window.importedId);
        }
        flight.value = null;
      },
    }) : null,
  ]) });
  app.use(pinia).use(vuetify).mount('#app');
  window.importLandingFixture = app;
  window.locateImport = async id => {
    panel.value.prepareImportLanding(id);
    await nextTick();
    return panel.value.beginImportLanding(id);
  };
  window.flyImport = async id => {
    window.importedId = id;
    window.lastLanding = null;
    panel.value.prepareImportLanding(id);
    const result = await resolveImportDestination({ documentId: id, preparedPanel: panel.value,
      getPanel: () => panel.value, getSidebarTarget: () => sidebar.value.getFlightTarget() });
    const target = result.target;
    window.importDestination = result.destination;
    if (!target) return null;
    flight.value = { origin: { left: 750, top: 400, width: 140, height: 180, borderRadius: 6 }, target, thumbUrl: '/api/test/thumbnail' };
    return target;
  };
  window.refreshImportGroups = () => { refreshKey.value++; };
}
