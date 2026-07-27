// ─────────────────────────────────────────────────────────────────────────────
// PaperMind Farb-Tokens (eine Quelle der Wahrheit für die Vuetify-Themes)
//
// Eine kuratierte Identität: feste kühle Slate-Neutrals (hell/dunkel) mit dem
// grünen PaperMind-Akzent. Die ausführliche --pm-*-Semantik (Tints,
// Hover/Active, Semantikfarben) lebt in theme.css.
// ─────────────────────────────────────────────────────────────────────────────

// ── Neutrals „Kontur" (accent-unabhängig) ────────────────────────────────────
// sRGB-Hex, abgeleitet aus docs/design/tokens.css (oklch). Vuetify parst kein
// oklch, deshalb hier die Hex-Entsprechungen – identisch zu den --pm-* in theme.css.
const NEUTRAL_DARK = {
  background: '#20292D',   // --pm-bg
  surface: '#333B3E',      // Karten-/Menü-/Dialogfläche = --pm-surface-card
  surface2: '#333B3E',
  surface3: '#3E484C',     // --pm-chip-bg / --pm-border
  surfaceHover: '#3A4346',
  sidebar: '#182226',      // --pm-sidebar-bg (tiefste Ebene)
  panelMid: '#283134',     // --pm-surface-list
  panelRight: '#1A2326',   // --pm-surface-reader (bewusst zurückgesetzt)
  card: '#333B3E',
  cardHover: '#3A4346',
  cardActive: '#1B494E',   // --pm-selected
  pdfStage: '#1A2326',
  text: '#F0F4F6',
  textMuted: '#A8B3B7',
  divider: '#3E484C',
  outline: '#3E484C',
  dividerSoft: '#3E484C',
  overlayScrim: 'rgba(0, 0, 0, 0.45)',
  shadow: '0 10px 30px rgba(0, 0, 0, 0.35)'
};

const NEUTRAL_LIGHT = {
  background: '#FFFFFF',   // --pm-bg (weißer Inhalt)
  surface: '#FFFFFF',      // Karten-/Menü-/Dialogfläche
  surface2: '#FFFFFF',
  surface3: '#E7EEF0',     // --pm-chip-bg
  surfaceHover: '#F0F6F7',
  sidebar: '#152A31',      // --pm-sidebar-bg (dunkle Tinte)
  panelMid: '#FFFFFF',     // --pm-surface-list
  panelRight: '#E7EEF0',   // --pm-surface-reader (getönt, klar sichtbar)
  card: '#FFFFFF',
  cardHover: '#F0F6F7',
  cardActive: '#DBF3F6',   // --pm-selected
  pdfStage: '#E7EEF0',
  text: '#0E181B',
  textMuted: '#535E62',
  divider: '#D8DFE1',
  outline: '#E7EEF0',
  dividerSoft: '#E7EEF0',
  overlayScrim: 'rgba(0, 0, 0, 0.42)',
  shadow: '0 10px 30px rgba(15, 23, 42, 0.10)'
};

// ── Fester grüner Akzent ─────────────────────────────────────────────────────
// Hell: kontraststarker Ton für Text/Buttons. Dunkel: leuchtender Ton.
const ACCENT_PRIMARY = Object.freeze({ light: '#006B75', dark: '#4FC5CB' });

function makeThemeColors(neutral, primary) {
  return { ...neutral, primary };
}

export const paperMindLight = makeThemeColors(NEUTRAL_LIGHT, ACCENT_PRIMARY.light);
export const paperMindDark = makeThemeColors(NEUTRAL_DARK, ACCENT_PRIMARY.dark);
