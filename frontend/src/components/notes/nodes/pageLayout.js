import { Node, mergeAttributes } from '@tiptap/vue-3';
import { Fragment } from '@tiptap/pm/model';
import { Selection } from '@tiptap/pm/state';
import {
  createNotePageLayout,
  flattenNotePageLayout,
  normalizeNotePageLayoutColumns,
  resizeNotePageLayout,
} from '../../../utils/noteLayouts.js';

/**
 * Findet den Layoutblock, in dem die aktuelle Auswahl liegt. Die absoluten
 * Grenzen ermöglichen blockweises Einfügen, Ändern und Auflösen – analog zu
 * den Transaktionen einer Tabelle.
 */
export function pageLayoutAtSelection(state) {
  const { $from } = state.selection;
  for (let depth = $from.depth; depth > 0; depth -= 1) {
    const node = $from.node(depth);
    if (node.type.name !== 'pageLayout') continue;
    return {
      node,
      from: $from.before(depth),
      to: $from.after(depth),
    };
  }
  return null;
}

function insertAdjacentLayout({ editor, state, tr, dispatch }, context, placement, columns) {
  const layout = editor.schema.nodeFromJSON(createNotePageLayout(columns));
  const position = placement === 'before' ? context.from : context.to;
  if (dispatch) {
    tr.insert(position, layout);
    setSelectionInsideLayout(tr, position);
    dispatch(tr.scrollIntoView());
  }
  return true;
}

function setSelectionInsideLayout(tr, layoutPosition) {
  const innerPosition = Math.min(layoutPosition + 3, tr.doc.content.size);
  tr.setSelection(Selection.near(tr.doc.resolve(innerPosition), 1));
}

function isEmptyPageLayout(node) {
  if (node?.type?.name !== 'pageLayout' || node.childCount < 1) return false;
  for (let columnIndex = 0; columnIndex < node.childCount; columnIndex += 1) {
    const column = node.child(columnIndex);
    if (column.childCount !== 1) return false;
    const onlyBlock = column.firstChild;
    if (onlyBlock?.type?.name !== 'paragraph' || onlyBlock.content.size !== 0) return false;
  }
  return true;
}

/** Frei platzierbarer Spaltenblock; davor und danach bleiben normale Blöcke. */
export const PageLayout = Node.create({
  name: 'pageLayout',
  group: 'block',
  content: 'layoutColumn{1,5}',
  defining: true,
  isolating: true,
  selectable: true,

  addAttributes() {
    return {
      columns: {
        default: 2,
        parseHTML: (element) => normalizeNotePageLayoutColumns(
          element.getAttribute('data-columns'),
          2,
        ),
        renderHTML: (attributes) => ({
          'data-columns': normalizeNotePageLayoutColumns(attributes.columns, 2),
        }),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-page-layout]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes({ 'data-page-layout': '' }, HTMLAttributes), 0];
  },

  addCommands() {
    return {
      insertPageLayout: (columns = 2) => (props) => {
        const context = pageLayoutAtSelection(props.state);
        if (context) {
          return insertAdjacentLayout(props, context, 'after', columns);
        }
        const layout = props.editor.schema.nodeFromJSON(createNotePageLayout(columns));
        if (props.dispatch) {
          props.tr.replaceSelectionWith(layout);
          const mappedSelection = props.tr.mapping.map(props.state.selection.from);
          let insertedAt = null;
          props.tr.doc.descendants((node, offset) => {
            if (
              node.type.name === 'pageLayout'
              && offset <= mappedSelection
              && offset + node.nodeSize >= mappedSelection - 1
            ) insertedAt = offset;
          });
          if (insertedAt !== null) setSelectionInsideLayout(props.tr, insertedAt);
          props.dispatch(props.tr.scrollIntoView());
        }
        return true;
      },
      setPageLayoutColumns: (columns) => ({ editor, state, tr, dispatch }) => {
        const context = pageLayoutAtSelection(state);
        if (!context) return false;
        const replacement = editor.schema.nodeFromJSON(
          resizeNotePageLayout(context.node.toJSON(), columns),
        );
        if (replacement.eq(context.node)) return true;
        if (dispatch) {
          tr.replaceWith(context.from, context.to, replacement);
          dispatch(tr.scrollIntoView());
        }
        return true;
      },
      insertPageLayoutAdjacent: (placement = 'after', columns = null) => (props) => {
        const context = pageLayoutAtSelection(props.state);
        if (!context) return false;
        const count = columns ?? context.node.childCount;
        return insertAdjacentLayout(props, context, placement, count);
      },
      unsetPageLayout: () => ({ editor, state, tr, dispatch }) => {
        const context = pageLayoutAtSelection(state);
        if (!context) return false;
        const blocks = flattenNotePageLayout(context.node.toJSON())
          .map((node) => editor.schema.nodeFromJSON(node));
        if (dispatch) {
          tr.replaceWith(context.from, context.to, Fragment.fromArray(blocks));
          dispatch(tr.scrollIntoView());
        }
        return true;
      },
      deleteEmptyPageLayout: () => ({ state, tr, dispatch }) => {
        const context = pageLayoutAtSelection(state);
        if (!context || !state.selection.empty || !isEmptyPageLayout(context.node)) return false;
        if (dispatch) {
          tr.delete(context.from, context.to);
          dispatch(tr.scrollIntoView());
        }
        return true;
      },
    };
  },

  addKeyboardShortcuts() {
    return {
      Backspace: () => this.editor.commands.deleteEmptyPageLayout(),
      Delete: () => this.editor.commands.deleteEmptyPageLayout(),
    };
  },
});

export const LayoutColumn = Node.create({
  name: 'layoutColumn',
  content: 'block+',
  defining: true,
  isolating: true,
  selectable: false,

  parseHTML() {
    return [{ tag: 'section[data-layout-column]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes({ 'data-layout-column': '' }, HTMLAttributes), 0];
  },
});

export default PageLayout;
