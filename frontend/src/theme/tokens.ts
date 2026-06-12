// ─────────────────────────────────────────────────────────────────────────────
// PaperMind Farb-Tokens (eine Quelle der Wahrheit für die Vuetify-Themes)
//
// Eine kuratierte Identität: FIXE kühle Slate-Neutrals (hell/dunkel) + 3
// umschaltbare Akzente (teal=Standard, violet, blue). Nur die Akzent-Primärfarbe
// wechselt je Variante – alle Flächen bleiben neutral. Die ausführliche
// --pm-*-Semantik (Tints, Hover/Active, Semantikfarben) lebt in theme.css.
// ─────────────────────────────────────────────────────────────────────────────

// ── Kühle Slate-Neutrals (accent-unabhängig) ─────────────────────────────────
const NEUTRAL_DARK = {
  background: '#0A0F19',
  surface: '#0E1420',
  surface2: '#141B28',
  surface3: '#1B2433',
  surfaceHover: '#1B2433',
  sidebar: '#0C111C',
  panelMid: '#0E1420',
  panelRight: '#0A0F19',
  card: '#141B28',
  cardHover: '#1B2433',
  cardActive: '#222E40',
  pdfStage: '#0A0F19',
  text: '#E6EBF2',
  textMuted: '#9AA4B2',
  divider: 'rgba(255, 255, 255, 0.08)',
  outline: 'rgba(255, 255, 255, 0.06)',
  dividerSoft: 'rgba(255, 255, 255, 0.08)',
  overlayScrim: 'rgba(0, 0, 0, 0.45)',
  shadow: '0 10px 30px rgba(0, 0, 0, 0.35)'
};

const NEUTRAL_LIGHT = {
  background: '#EEF2F8',
  surface: '#F7F9FC',
  surface2: '#FFFFFF',
  surface3: '#E8EFF7',
  surfaceHover: '#F3F6FB',
  sidebar: '#E9EEF5',
  panelMid: '#F7F9FC',
  panelRight: '#F1F4FA',
  card: '#FFFFFF',
  cardHover: '#F3F6FB',
  cardActive: '#E8EFF7',
  pdfStage: '#F1F4FA',
  text: '#16202E',
  textMuted: '#5A6573',
  divider: 'rgba(15, 23, 42, 0.10)',
  outline: 'rgba(15, 23, 42, 0.06)',
  dividerSoft: 'rgba(15, 23, 42, 0.08)',
  overlayScrim: 'rgba(0, 0, 0, 0.42)',
  shadow: '0 10px 30px rgba(15, 23, 42, 0.10)'
};

// ── Akzent-Primärfarben (das Einzige, was je Variante wechselt) ───────────────
// Hell: kontraststarker Ton für Text/Buttons. Dunkel: leuchtender Ton.
const ACCENT_PRIMARY = Object.freeze({
  teal: { light: '#0E7490', dark: '#22D3EE' },
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
