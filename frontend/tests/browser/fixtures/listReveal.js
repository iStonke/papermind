import { createApp, h, reactive, withDirectives, nextTick } from 'vue';
import { vListReveal } from '../../../src/directives/listReveal.js';
export function mount() {
  const state = reactive({ key: 'initial', ready: false, hidden: false, disabled: false, items: [] });
  window.listReveal = state;
  window.listRevealNextTick = nextTick;
  createApp({ render: () => h('div', { class: state.disabled ? 'pm-no-animations' : '' }, [
    withDirectives(h('section', { id: 'list', style: { display: state.hidden ? 'none' : 'block', width: '340px', height: '240px', overflow: 'auto' } }, state.items.map(item => h('div', { key: item.id, 'data-row': item.id, style: 'height:52px;box-sizing:border-box;padding:12px;border:1px solid #ddd' }, item.title))), [[vListReveal, { key: state.key, ready: state.ready, selector: '[data-row]' }]])
  ]) }).mount('#app');
}
