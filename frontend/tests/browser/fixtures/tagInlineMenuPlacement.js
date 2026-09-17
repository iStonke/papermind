import { createApp, h, ref } from 'vue';
import { createVuetify } from 'vuetify';
import TagInlineEditor from '../../../src/components/TagInlineEditor.vue';
import '../../../src/workspaces/documents/workspace.css';

export function mountTagInlineMenu(placement = 'bottom') {
  const names = ref(['Schulung', 'ISTBQ']);
  const search = ref('');
  const hostStyle = placement === 'bottom'
    ? 'position:fixed;left:240px;bottom:20px;width:560px;padding:12px'
    : 'position:fixed;left:240px;top:20px;width:560px;padding:12px';
  const menuProps = {
    location: 'bottom start', origin: 'top start', offset: 6,
    attach: 'body', minWidth: 260, maxWidth: 360, maxHeight: 180,
    closeOnContentClick: false, contentClass: 'pm-menu--details-tags',
  };

  createApp({
    setup() {
      return () => h('div', { class: 'pm-drawer-body', style: hostStyle }, [
        h(TagInlineEditor, {
          modelValue: names.value,
          search: search.value,
          items: ['Agiles Testen'],
          menuProps,
          'onUpdate:modelValue': (value) => { names.value = value; },
          'onUpdate:search': (value) => { search.value = value; },
        }),
      ]);
    },
  }).use(createVuetify()).mount('#app');
}
