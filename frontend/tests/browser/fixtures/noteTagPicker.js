import { createApp, h, ref } from 'vue';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import NoteTagBar from '../../../src/components/notes/NoteTagBar.vue';
export function mountTagPicker() {
  const ids = ref(['1']);
  const tags = ref([{ id: '1', name: 'Vertrag' }, { id: '2', name: 'Abstimmung' }]);
  createApp({ setup: () => () => h(NoteTagBar, {
    summarized: true, tagIds: ids.value, allTags: tags.value,
    createTagByName: async name => { tags.value.push({ id: '3', name }); return '3'; },
    'onUpdate:tagIds': value => { ids.value = value; },
  }) }).use(createVuetify()).mount('#app');
}
