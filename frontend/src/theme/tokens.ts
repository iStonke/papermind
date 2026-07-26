// ─────────────────────────────────────────────────────────────────────────────
// PaperMind Farb-Tokens (eine Quelle der Wahrheit für die Vuetify-Themes)
//
// Eine kuratierte Identität: FIXE kühle Slate-Neutrals (hell/dunkel) + 3
// umschaltbare Akzente (teal=Standard, violet, blue). Nur die Akzent-Primärfarbe
// wechselt je Variante – alle Flächen bleiben neutral. Die ausführliche
// --pm-*-Semantik (Tints, Hover/Active, Semantikfarben) lebt in theme.css.
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
  panelRight: '#F0F6F7',   // --pm-surface-reader (leicht getönt)
  card: '#FFFFFF',
  cardHover: '#F0F6F7',
  cardActive: '#DBF3F6',   // --pm-selected
  pdfStage: '#F0F6F7',
  text: '#0E181B',
  textMuted: '#535E62',
  divider: '#D8DFE1',
  outline: '#E7EEF0',
  dividerSoft: '#E7EEF0',
  overlayScrim: 'rgba(0, 0, 0, 0.42)',
  shadow: '0 10px 30px rgba(15, 23, 42, 0.10)'
};

// ── Akzent-Primärfarben (das Einzige, was je Variante wechselt) ───────────────
// Teal = Kontur-Marke (nur Zustandsfarbe). Hell: kontraststarker Ton für
// Text/Buttons. Dunkel: leuchtender Ton (Schrift darauf via --pm-on-accent).
const ACCENT_PRIMARY = Object.freeze({
  teal: { light: '#006B75', dark: '#4FC5CB' },
  violet: { light: '#7C3AED', dark: '#A78BFA' },
  blue: { light: '#2563EB', dark: '#60A5FA' }
});

function makeThemeColors(neutral, primary) {
  return { ...neutral, primary };
}

// Standard-Export (Teal) für die statische Vuetify-Initialisierung.
export const paperMindLight = makeThemeColors(NEUTRAL_LIGHT, ACCENT_PRIMARY.teal.light);
export const paperMindDark = makeThemeColors(NEUTRAL_DARK, ACCENT_PRIMARY.teal.dark);

export const paperMindColorVariants = Object.freeze({
  teal: { light: paperMindLight, dark: paperMindDark },
  violet: {
    light: makeThemeColors(NEUTRAL_LIGHT, ACCENT_PRIMARY.violet.light),
    dark: makeThemeColors(NEUTRAL_DARK, ACCENT_PRIMARY.violet.dark)
  },
  blue: {
    light: makeThemeColors(NEUTRAL_LIGHT, ACCENT_PRIMARY.blue.light),
    dark: makeThemeColors(NEUTRAL_DARK, ACCENT_PRIMARY.blue.dark)
  }
});

export const PAPER_MIND_COLOR_VARIANT_VALUES = Object.freeze(Object.keys(paperMindColorVariants));

export function resolvePaperMindColorVariant(variant) {
  return Object.prototype.hasOwnProperty.call(paperMindColorVariants, variant) ? variant : 'teal';
}

function assignVuetifyThemeColors(target, source) {
  target.background = source.background;
  target.surface = source.surface;
  target.primary = source.primary;
  target['on-background'] = source.text;
  target['on-surface'] = source.text;
  target['surface-2'] = source.surface2;
  target['surface-3'] = source.surface3;
  target['surface-hover'] = source.surfaceHover;
  target['panel-left'] = source.sidebar;
  target['panel-mid'] = source.panelMid;
  target['panel-right'] = source.panelRight;
  target.card = source.card;
  target['card-hover'] = source.cardHover;
  target['card-active'] = source.cardActive;
  target['text-muted'] = source.textMuted;
  target.divider = source.divider;
  target.outline = source.outline;
  target['divider-soft'] = source.dividerSoft;
}

export function applyPaperMindVuetifyColors(theme, variant) {
  const resolvedVariant = resolvePaperMindColorVariant(variant);
  const variantTokens = paperMindColorVariants[resolvedVariant];
  assignVuetifyThemeColors(theme.themes.value.light.colors, variantTokens.light);
  assignVuetifyThemeColors(theme.themes.value.dark.colors, variantTokens.dark);
  return resolvedVariant;
}
