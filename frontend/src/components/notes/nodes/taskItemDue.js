/*
 * PaperMindTaskItem — erweitert das Standard-TaskItem um ein `dueDate`-Attribut
 * (ISO-Datum) und eine Vue-NodeView mit Kalender-Chip (TaskItemView.vue). Das
 * Datum wird als data-due-date gerendert und im ProseMirror-JSON (attrs.dueDate)
 * gespeichert; das Backend extrahiert es beim Speichern nach note_task (M6 B2).
 */
import TaskItem from '@tiptap/extension-task-item';
import { VueNodeViewRenderer } from '@tiptap/vue-3';
import TaskItemView from './TaskItemView.vue';

export const PaperMindTaskItem = TaskItem.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      dueDate: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-due-date') || null,
        renderHTML: (attributes) =>
          attributes.dueDate ? { 'data-due-date': attributes.dueDate } : {},
      },
    };
  },

  addNodeView() {
    return VueNodeViewRenderer(TaskItemView);
  },
});

export default PaperMindTaskItem;
