import { createApp, h, reactive, ref } from 'vue';
import DocumentOcrDetails from '../../../src/components/DocumentOcrDetails.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export function mount({ theme = 'light', tone = 'done', document = {} } = {}) {
  const data = reactive({ id: 'document-a', text_source: 'ocr', ocr_quality_status: 'good', ocr_confidence_score: 93.2,
    ocr_processing_seconds: 12.4, ocr_quality_message: 'OCR-Qualität gut.', text_content: 'Ein erkannter Text.\nZweite Zeile.',
    jobs: [{ type: 'OCR', status: 'done', created_at: '2026-10-30T09:00:00Z', finished_at: '2026-10-30T09:00:13Z' }], ...document });
  const status = reactive({ tone, text: tone === 'warning' ? 'OCR unsicher' : tone === 'failed' ? 'OCR fehlgeschlagen' : 'OCR', icon: 'mdi-check-circle-outline' });
  const retries = ref(0), headerClicks = ref(0);
  vuetify.theme.global.name.value = theme;
  const app = createApp({ render: () => h('div', { class: ['papermind-app', `v-theme--${theme}`], style: 'min-height:100vh;padding:36px;background:var(--pm-app-bg);color:var(--pm-text)' }, [
    h('div', { class: 'details-drawer__header', onClick: () => headerClicks.value++, style: 'margin:40px auto;max-width:900px' },
      h(DocumentOcrDetails, { document: data, status, busy: status.tone === 'progress', onRetry: () => retries.value++ }))
  ]) }).use(vuetify);
  app.mount('#app');
  window.ocrDemo = { data, status, retries, headerClicks };
}
