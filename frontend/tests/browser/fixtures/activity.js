import { createApp, h } from 'vue';
import ActivityIndicator from '../../../src/components/ActivityIndicator.vue';
import vuetify from '../../../src/plugins/vuetify.js';
export function mountActivity(theme = 'light') {
  vuetify.theme.global.name.value = theme;
  createApp({ render: () => h(ActivityIndicator) }).use(vuetify).mount('#app');
}
