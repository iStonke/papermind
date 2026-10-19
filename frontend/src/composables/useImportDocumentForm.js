import { computed } from 'vue';
import { ensureImportForm } from '../utils/importWorkflow.js';

export function useImportDocumentForm(document) {
  const form = computed(() => ensureImportForm(document.value));
  const fields = {};
  for (const [name, key] of Object.entries({ docDate: 'date', docCategory: 'category', docNote: 'note', docCorrespondentId: 'correspondentId', docRetention: 'retention' })) {
    fields[name] = computed({ get: () => form.value[key], set: value => { form.value[key] = value; } });
  }
  for (const field of ['Title', 'Date', 'Category', 'Tags', 'Note', 'Correspondent', 'Retention']) {
    const key = field.toLowerCase();
    fields[`doc${field}Touched`] = computed({
      get: () => Boolean(form.value.touched[key]),
      set: value => {
        form.value.touched[key] = value;
        if (value) form.value.revisions[key] = (form.value.revisions[key] || 0) + 1;
      },
    });
    fields[`doc${field}AiFilled`] = computed({ get: () => Boolean(form.value.aiFilled[key]), set: value => { form.value.aiFilled[key] = value; } });
  }
  return { ...fields, importForm: form };
}
