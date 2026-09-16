import { createApp, h, reactive, computed } from 'vue';
import NoteReviewPanel from '../../../src/components/notes/NoteReviewPanel.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountDecisions() {
  const review = reactive({ loading: false, error: '', empty: false, changes: [1, 2, 3].map(id => ({ id, number: id, cat: 'fix', revised: `Vorschlag ${id}`, reason: 'Eine kurze Erklärung.', summary: 'Die Schreibweise korrigieren.' })), status: {}, showMarks: true, filter: 'open', sort: 'order', focusId: 1 });
  const cards = computed(() => review.changes.filter(c => review.filter === 'all' || review.status[c.id] !== 'rejected'));
  const noop = () => {};
  window.decisions = [];
  const controller = { review, effectiveFocusId: computed(() => review.focusId), reviewCards: cards, reviewSections: computed(() => [{key:'open',label:'Offen',cards:cards.value}]), openCount: computed(() => cards.value.length), rejectedCount: computed(() => 0),
    acceptChange: id => { window.decisions.push(['accept',id]); review.changes = review.changes.filter(c => c.id !== id); },
    rejectChange: id => { window.decisions.push(['reject',id]); review.status[id] = 'rejected'; },
    reopenChange: noop, setFilter: noop, revealChange: id => { review.focusId = id; }, clearFocus: noop, toggleMarks: noop, setSort: noop, regenerateReview: noop, closeReview: noop };
  const app = createApp({render: () => h(NoteReviewPanel,{controller})}).use(vuetify);
  app.mount('#app');
  window.reviewFixture = {review, unmount: () => app.unmount()};
}
