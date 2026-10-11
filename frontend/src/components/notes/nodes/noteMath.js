import { InputRule } from '@tiptap/core';
import { BlockMath, InlineMath } from '@tiptap/extension-mathematics';
import 'katex/dist/katex.min.css';

// Fehlerhaftes LaTeX wird rot angezeigt statt die Darstellung abzubrechen.
export const NOTE_KATEX_OPTIONS = Object.freeze({ throwOnError: false, strict: 'ignore' });

// Greift beim Tippen des schließenden `$`. Wie beim Markdown-Import: kein
// Leerzeichen direkt innen und kein `$`/Buchstabe/Ziffer vor dem öffnenden
// Zeichen – so bleiben „5 $ bis 10 $" und `$$…$$` (eigene Regel) unberührt.
export const SINGLE_DOLLAR_INPUT = /(?<![\p{L}\p{N}$\\])\$([^\s$](?:[^$\n]*?[^\s$\\])?)\$$/u;

const NoteInlineMath = InlineMath.extend({
  addInputRules() {
    return [
      ...(this.parent?.() || []),
      new InputRule({
        find: SINGLE_DOLLAR_INPUT,
        handler: ({ state, range, match }) => {
          state.tr.replaceWith(range.from, range.to, this.type.create({ latex: match[1].trim() }));
        },
      }),
    ];
  },
});

/**
 * Formel-Knoten (inline `$…$`, Block `$$…$$`) mit KaTeX. `onEdit` erhält
 * Knoten + Position, wenn eine Formel angeklickt wird (nur im bearbeitbaren
 * Editor gesetzt).
 */
export function createNoteMathExtensions({ onEdit = null } = {}) {
  const onClick = onEdit ? (node, pos) => onEdit(node, pos) : undefined;
  return [
    NoteInlineMath.configure({ katexOptions: NOTE_KATEX_OPTIONS, onClick }),
    // Die Extension reicht die Optionen unverändert an KaTeX weiter; Blöcke
    // brauchen den Anzeigemodus (größere Brüche, Summen mit Grenzen oben/unten).
    BlockMath.configure({ katexOptions: { ...NOTE_KATEX_OPTIONS, displayMode: true }, onClick }),
  ];
}
