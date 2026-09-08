/*
 * CheckList / CheckListItem — neutrale Checkliste OHNE Aufgaben-Charakter.
 *
 * Sieht aus wie eine Aufgabenliste (abhakbare Punkte), wird aber bewusst als
 * eigener Node-Typ (`checkList` / `checkListItem`) geführt. Dadurch:
 *   - taucht sie NICHT in `note_task` auf (Backend `extract_note_tasks` matcht
 *     ausschließlich `taskItem`) und läuft nie in die Aufgaben-Übersicht,
 *   - bleibt beim Speichern erhalten (Backend filtert body_json nicht).
 *
 * Gedacht für Checklisten wie Testfall-Kriterien, Packlisten o. Ä., die kein
 * offenes To-do darstellen. Echte Aufgaben nutzen weiterhin `taskItem`
 * (siehe taskItemDue.js).
 */
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { VueNodeViewRenderer } from '@tiptap/vue-3';
import CheckListItemView from './CheckListItemView.vue';

export const CheckList = TaskList.extend({
  name: 'checkList',

  addOptions() {
    return {
      ...this.parent?.(),
      itemTypeName: 'checkListItem',
      HTMLAttributes: {},
    };
  },

  // Eigener Toggle-Befehl, damit es keine Kollision mit `toggleTaskList` gibt.
  addCommands() {
    return {
      toggleCheckList:
        () =>
        ({ commands }) =>
          commands.toggleList(this.name, this.options.itemTypeName),
    };
  },
});

export const CheckListItem = TaskItem.extend({
  name: 'checkListItem',

  addOptions() {
    return {
      ...this.parent?.(),
      nested: true,
      taskListTypeName: 'checkList',
      HTMLAttributes: {},
    };
  },

  addNodeView() {
    return VueNodeViewRenderer(CheckListItemView);
  },
});

export default CheckList;
