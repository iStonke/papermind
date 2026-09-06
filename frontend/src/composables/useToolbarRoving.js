import { onBeforeUnmount, watch } from 'vue';

/**
 * „Roving tabindex" für eine `role="toolbar"`-Leiste (ARIA Toolbar Pattern).
 *
 * Standardmäßig ist jeder Button ein eigener Tab-Stopp — eine Leiste mit vier
 * Menü-Buttons kostet den Tastaturnutzer also vier Tab-Anschläge, bevor er den
 * Editor erreicht. Dieses Composable macht die Buttons zu EINEM Tab-Stopp:
 * genau ein Button ist tabbable (`tabindex=0`), der Rest `tabindex=-1`; zwischen
 * ihnen wird mit Pfeil links/rechts sowie Pos1/Ende navigiert.
 *
 * Bewusst NICHT einbezogen werden Text-/Editierfelder (z. B. das KI-Feld) — dort
 * müssen die Pfeiltasten den Cursor bewegen, also bleibt ein solches Feld ein
 * eigenständiger Tab-Stopp. Ebenso werden Buttons in geöffneten Dropdowns/Menüs
 * ausgeklammert, damit deren eigene Navigation nicht gekapert wird.
 *
 * Angebunden wird über einen `watch` auf die Template-Ref, damit es auch dann
 * greift, wenn die Leiste erst nach dem Mount erscheint (z. B. `v-if="workspace"`):
 *   const toolbarEl = ref(null);
 *   useToolbarRoving(toolbarEl);
 */

const NON_ROVING_SEL =
  '.note-editor__toolbar-dropdown, [role="menu"], [role="listbox"], [role="dialog"]';

export function useToolbarRoving(toolbarRef) {
  let bound = null;

  // Die navigierbaren Buttons: nicht deaktiviert und nicht Teil eines geöffneten
  // Dropdowns/Menüs. Wird bei jedem Tastendruck frisch ermittelt, damit
  // Kompaktmodus & wechselnde Buttonsätze automatisch passen. Bewusst KEIN
  // Layout-basierter Sichtbarkeits-Check (offsetParent/getClientRects): beim ersten
  // Binden kann die Leiste noch ungelayoutet sein, dann würde init() leer ausgehen
  // und nie wieder laufen. Geschlossene Dropdowns sind ohnehin per v-if aus dem DOM.
  function items(el) {
    return Array.from(el.querySelectorAll('button:not([disabled])')).filter(
      (btn) => !btn.closest(NON_ROVING_SEL),
    );
  }

  function setActive(el, target) {
    for (const btn of items(el)) {
      btn.tabIndex = btn === target ? 0 : -1;
    }
  }

  function init(el) {
    const list = items(el);
    if (list.length && !list.some((btn) => btn.tabIndex === 0)) {
      setActive(el, list[0]);
    }
  }

  function onKeydown(event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;

    // In Text-/Editierfeldern und offenen Menüs bewegen die Pfeile den Cursor
    // bzw. navigieren das Menü — hier nicht eingreifen.
    const target = event.target;
    if (
      target
      && (target.tagName === 'INPUT'
        || target.tagName === 'TEXTAREA'
        || target.isContentEditable)
    ) {
      return;
    }
    if (target && target.closest && target.closest(NON_ROVING_SEL)) return;

    const el = bound;
    if (!el) return;
    const list = items(el);
    if (!list.length) return;

    const current = list.indexOf(document.activeElement);
    let next;
    if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = list.length - 1;
    else if (event.key === 'ArrowRight') next = current < 0 ? 0 : (current + 1) % list.length;
    else next = current < 0 ? list.length - 1 : (current - 1 + list.length) % list.length;

    event.preventDefault();
    setActive(el, list[next]);
    list[next].focus();
  }

  // Nach Maus-/Programmfokus den tabbable-Button nachziehen, damit der nächste
  // Tab-Ein-/Ausstieg wieder an der zuletzt benutzten Stelle andockt.
  function onFocusin(event) {
    const el = bound;
    if (!el) return;
    const btn = event.target.closest && event.target.closest('button');
    if (btn && items(el).includes(btn)) setActive(el, btn);
  }

  function bind(el) {
    if (bound === el) return;
    unbind();
    if (!el) return;
    bound = el;
    init(el);
    el.addEventListener('keydown', onKeydown);
    el.addEventListener('focusin', onFocusin);
  }

  function unbind() {
    if (!bound) return;
    bound.removeEventListener('keydown', onKeydown);
    bound.removeEventListener('focusin', onFocusin);
    bound = null;
  }

  // `immediate` fängt den Fall ab, dass die Ref schon gesetzt ist; der Watcher
  // fängt das spätere Erscheinen (v-if) sowie ein Neu-Rendern der Leiste ab.
  watch(toolbarRef, (el) => bind(el || null), { immediate: true, flush: 'post' });

  onBeforeUnmount(unbind);
}
