import { createApp, h, reactive, ref } from 'vue';
import DocumentKnowledgeDetails from '../../../src/components/DocumentKnowledgeDetails.vue';
import DocumentOcrDetails from '../../../src/components/DocumentOcrDetails.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export function mount({ theme = 'light', document = {} } = {}) {
  const data = reactive({ id: 'document-a', display_name: 'Beitragsrechnung Januar 2024', text_source: 'ocr',
    ai_status: 'done', ai_document_type: 'Beitragsrechnung', ai_document_date: '2024-01-01', ai_sender: 'HUK-COBURG',
    ai_recipient: 'Jan Steinke', ai_amount: 183.5, ai_currency: 'EUR',
    ai_summary: 'Beitragsrechnung für die Kfz-Versicherung im Januar 2024. Der Beitrag beträgt 183,50 Euro.',
    ai_suggested_tags: ['Kfz-Versicherung', 'Beitragsrechnung'], ai_processed_at: '2026-10-30T10:00:00Z', ...document });
  const busy = ref(false), headerClicks = ref(0), completions = ref([]), completionError = ref('');
  const saves = ref([]), saveFailure = ref(''), saveHandler = ref(null);
  const correspondents = [{ title: 'HUK-COBURG', value: 'huk' }, { title: 'KMTV', value: 'kmtv' }];
  async function saveChanges(id, patch) {
    saves.value.push({ id, patch });
    if (saveFailure.value) throw new Error(saveFailure.value);
    if (saveHandler.value) await saveHandler.value(id, patch);
    if (data.id === id) Object.assign(data, patch, {
      correspondent_name: correspondents.find(item => item.value === (patch.correspondent_id ?? data.correspondent_id))?.title || '',
      flags: { ...data.flags, manual_metadata_fields: [...new Set([...(data.flags?.manual_metadata_fields || []), ...Object.keys(patch)])] }
    });
  }
  vuetify.theme.global.name.value = theme;
  const app = createApp({ render: () => h('div', { class: ['papermind-app', `v-theme--${theme}`], style: 'min-height:100vh;padding:36px;background:var(--pm-app-bg);color:var(--pm-text)' }, [
    h('div', { class: 'details-drawer__header', onClick: () => headerClicks.value++, style: 'display:flex;align-items:center;gap:18px;margin:20px auto;max-width:900px' }, [
      h(DocumentOcrDetails, { document: data, status: { tone: 'done', text: 'OCR', icon: 'mdi-check-circle-outline' } }),
      h(DocumentKnowledgeDetails, { document: data, busy: busy.value, completionError: completionError.value, saveChanges,
        documentTypes: ['Rechnung', 'Beitragsrechnung'], correspondents, onComplete: id => completions.value.push(id) })
    ])
  ]) }).use(vuetify);
  app.mount('#app');
  window.knowledgeDemo = { data, busy, headerClicks, completions, completionError, saves, saveFailure, saveHandler };
}
