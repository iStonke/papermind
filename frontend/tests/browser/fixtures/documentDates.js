import { createApp, h, reactive, ref } from 'vue';
import DocumentDateDetails from '../../../src/components/DocumentDateDetails.vue';
import DocumentKnowledgeDetails from '../../../src/components/DocumentKnowledgeDetails.vue';
import DocumentOcrDetails from '../../../src/components/DocumentOcrDetails.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export function mount({ theme = 'light', document = {} } = {}) {
  const data = reactive({ id: 'document-a', created_at: '2026-08-24T01:05:00+02:00', document_date: '2018-10-16',
    updated_at: '2026-11-01T19:30:00Z', display_name: 'Sportangebot Oktober 2018', ai_status: 'done',
    text_source: 'ocr', ocr_quality_status: 'good', ocr_confidence_score: 93.2, ...document });
  const headerClicks = ref(0);
  vuetify.theme.global.name.value = theme;
  const dot = () => h('span', { class: 'details-drawer__meta-dot', 'aria-hidden': 'true' });
  createApp({ render: () => h('div', { class: ['papermind-app', `v-theme--${theme}`], style: 'min-height:100vh;padding:32px;background:var(--pm-app-bg);color:var(--pm-text)' }, [
    h('div', { class: 'details-drawer__meta-line', style: 'display:flex;flex-wrap:wrap;overflow:visible', onClick: () => headerClicks.value++ }, [
      h('span', { class: 'details-drawer__meta-part' }, '1 Seite'), dot(), h(DocumentDateDetails, { document: data }), dot(),
      h(DocumentKnowledgeDetails, { document: data }), dot(),
      h(DocumentOcrDetails, { document: data, status: { tone: 'done', text: 'OCR', icon: 'mdi-check-circle-outline' } })
    ])
  ]) }).use(vuetify).mount('#app');
  window.documentDatesDemo = { data, headerClicks };
}
