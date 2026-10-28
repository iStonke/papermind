import { createApp, h, reactive, ref, nextTick } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import { createVuetify } from 'vuetify';
import Swap from '../../../src/components/PreviewSwap.vue';
import Drawer from '../../../src/components/DocumentPreviewLayout.vue';
import List from '../../../src/components/DocumentListPanel.vue';
import { useDocumentStore } from '../../../src/stores/documents.js';
import '../../../src/workspaces/documents/workspace.css';
export function mount() {
    const style = document.createElement('style'); style.textContent = '.document-list-shell { height:500px;overflow:auto }'; document.head.append(style);
    const pinia = createPinia(); setActivePinia(pinia);
    const store = useDocumentStore();
    store.documents = Array.from({ length: 300 }, (_, i) => ({ id: `doc-${i}`, original_filename: `Dokument ${i}.pdf`, tags: [] }));
    store.selectedDocumentId = 'doc-0';
    const state = reactive({ key: 'a', open: false, filter: 'all' });
    const swap = ref(null);
    window.motion = { state, store, reveal: () => swap.value.reveal(state.key), nextTick };
    const app = createApp({ render: () => h('main', [
      h('div', { style: 'height:450px;width:500px;display:flex' }, [h(Swap, { ref: swap, transitionKey: state.key }, {
        default: () => h('div', { key: state.key, class: 'pdf-preview pdf-preview--document-ready', style: 'flex:1;background:#ccc;display:flex' }, [
          h('canvas', { width: 100, height: 100, style: 'width:100px;height:100px', ref: el => { if (el) { const c = el.getContext('2d'); c.fillStyle = state.key === 'a' ? 'red' : 'blue'; c.fillRect(0, 0, 100, 100); } } })
        ])
      })]),
      h('div', { style: 'height:450px;width:500px' }, [h(Drawer, { showDrawer: true, floatingCard: true, isOpen: state.open }, {
        viewer: () => h('div', 'PDF'), 'drawer-header': () => h('div', { style: 'height:72px' }, 'Details'),
        'drawer-body': () => h('div', Array.from({ length: 4 }, (_, i) => h('div', { class: 'pm-metadata-row', style: 'height:48px' }, [h('input', { value: `Feld ${i}` })])))
      })]),
      h('div', { style: 'height:500px;width:500px' }, [h(List, { motionKey: state.filter, onSelectDocument: id => { store.selectedDocumentId = id; } })])
    ]) });
    app.use(pinia); app.use(createVuetify()); app.mount('#app');
}
