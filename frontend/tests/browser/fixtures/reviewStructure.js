import { createApp, h, shallowRef, reactive, onMounted } from 'vue';
import { Editor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { TableKit } from '@tiptap/extension-table';
import { Callout } from '../../../src/components/notes/nodes/callout.js';
import { NoteReviewDecorations } from '../../../src/components/notes/extensions/reviewDecorations.js';
import { useNoteReview } from '../../../src/components/notes/composables/useNoteReview.js';
import { createNoteOverlayCoordinator } from '../../../src/components/notes/composables/noteOverlayCoordinator.js';
import NoteReviewPanel from '../../../src/components/notes/NoteReviewPanel.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountStructureReview({ deferred = false } = {}) {
  createApp({ setup() {
    const editor = shallowRef(new Editor({extensions:[StarterKit,TableKit,Callout,NoteReviewDecorations],content:'<p>Davor</p><p>Name: Anna</p><p>Rolle: Leitung</p><p>Vor dem Speichern prüfen.</p><p>Danach</p>'}));
    const before = editor.value.getJSON();
    const c = useNoteReview({editor,props:reactive({noteId:'test',aiAvailable:true,readonly:false}),overlays:createNoteOverlayCoordinator(),onCheckpoint:()=>{},stream:async(payload,{onEvent,signal})=>{
      window.structureSignal = signal;
      if (deferred) await new Promise(resolve => { window.finishStructureStream = resolve; });
      window.structurePayload = payload;
      onEvent({type:'delta',text:JSON.stringify({changes:[
        {id:1,cat:'format',block_ids:['b2','b3'],anchor:'Name: Anna\nRolle: Leitung',revised:'| Name | Rolle |\n| --- | --- |\n| Anna | Leitung |',summary:'Namen und Rollen in einer Tabelle gegenüberstellen.',reason:'Die Angaben lassen sich als Tabelle vergleichen.'},
        {id:2,cat:'format',block_ids:['b4'],anchor:'Vor dem Speichern prüfen.',revised:'> [!WARNING]\n> Vor dem Speichern prüfen.',summary:'Den Absatz als Warnhinweis hervorheben.',reason:'Ein wichtiger Hinweis wird als Block hervorgehoben.'},
      ]})});
    }});
    window.structureReview = {editor:editor.value,c,before};
    onMounted(()=>c.startReview());
    return ()=>h('div',{style:'display:flex;height:750px;gap:30px'},[h(EditorContent,{editor:editor.value,style:'width:500px'}),h('div',{style:'width:380px'},[h(NoteReviewPanel,{controller:c})])]);
  }}).use(vuetify).mount('#app');
}
