import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import { VApp } from 'vuetify/components';
import vuetify from '../../../src/plugins/vuetify.js';
import PdfPreview from '../../../src/components/PdfPreview.vue';
import DocumentReader from '../../../src/components/DocumentReader.vue';
import '../../../src/theme/theme.css';

export function mountPreviewToolbar({ reader = false } = {}) {
  createApp({ render: () => h(VApp, null, { default: () => h('div', { style: 'height:calc(100vh - 24px);margin:12px' }, [
    h(reader ? DocumentReader : PdfPreview, { src: '/toolbar-test.pdf', title: 'Testdokument' }),
  ]) }) }).use(createPinia()).use(vuetify).mount('#app');
  window.previewToolbarFixture = { setTheme: mode => vuetify.theme.change(mode) };
}
