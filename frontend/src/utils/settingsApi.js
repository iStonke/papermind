export function buildThemeModePatch(themeMode) {
  return { ui: { theme_mode: themeMode } };
}

export function buildColorVariantPatch(colorVariant) {
  return { ui: { color_variant: colorVariant } };
}

export function buildShowFilenameSuffixPatch(enabled) {
  return { ui: { showFilenameSuffix: Boolean(enabled) } };
}

export function buildDrawerRememberStatePatch(enabled) {
  return { ui: { drawerRememberState: Boolean(enabled) } };
}

export function buildTagDrawerRememberStatePatch(enabled) {
  return { ui: { tagDrawerRememberState: Boolean(enabled) } };
}

export function buildSidebarShowRecentPatch(enabled) {
  return { ui: { sidebar_show_recent: Boolean(enabled) } };
}

export function buildSidebarShowUntaggedPatch(enabled) {
  return { ui: { sidebar_show_untagged: Boolean(enabled) } };
}

export function buildSidebarShowNoTextPatch(enabled) {
  return { ui: { sidebar_show_no_text: Boolean(enabled) } };
}

export function buildSidebarShowChatPatch(enabled) {
  return { ui: { sidebar_show_chat: Boolean(enabled) } };
}

// Konfigurierbare Seitenleisten-Sektionen (Reihenfolge + harte Sichtbarkeit).
// Reihenfolge entspricht der Standard-Anzeigereihenfolge in der Seitenleiste.
export const SIDEBAR_SECTION_KEYS = Object.freeze(['ordner', 'tags', 'kategorien']);

const SIDEBAR_SECTION_LABELS = Object.freeze({
  ordner: 'Ordner',
  tags: 'Tags',
  kategorien: 'Dokumenttypen'
});

export function sidebarSectionLabel(key) {
  return SIDEBAR_SECTION_LABELS[key] || String(key || '');
}

/**
 * Dedupliziert nach Key (erstes Vorkommen gewinnt) und ergänzt fehlende
 * Sektionen in der Standardreihenfolge, sodass immer genau alle bekannten
 * Sektionen vorhanden sind. Spiegelt die Backend-Normalisierung.
 */
export function normalizeSidebarSections(sections) {
  const result = [];
  const seen = new Set();
  for (const section of Array.isArray(sections) ? sections : []) {
    const key = String(section?.key || '');
    if (!SIDEBAR_SECTION_KEYS.includes(key) || seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push({ key, visible: section?.visible !== false });
  }
  for (const key of SIDEBAR_SECTION_KEYS) {
    if (!seen.has(key)) {
      result.push({ key, visible: true });
    }
  }
  return result;
}

export function buildSidebarSectionsPatch(sections) {
  return { ui: { sidebar_sections: normalizeSidebarSections(sections) } };
}

function clampSidebarMax(value) {
  const parsed = Math.round(Number(value));
  if (!Number.isFinite(parsed)) return 5;
  return Math.min(50, Math.max(0, parsed));
}

export function buildSidebarMaxTagsPatch(count) {
  return { ui: { sidebar_max_tags: clampSidebarMax(count) } };
}

export function buildSidebarMaxCategoriesPatch(count) {
  return { ui: { sidebar_max_categories: clampSidebarMax(count) } };
}

export function buildAutoOcrPatch(enabled) {
  return { documents: { auto_ocr: Boolean(enabled) } };
}

export function buildAutoTaggingPatch(enabled) {
  return { documents: { auto_tagging: Boolean(enabled) } };
}

export function buildOcrBackfillEnabledPatch(enabled) {
  return { documents: { ocr_backfill_enabled: Boolean(enabled) } };
}

export function buildAutoOpenImportInboxPatch(enabled) {
  return { documents: { auto_open_import_inbox: Boolean(enabled) } };
}

export function buildSortOrderPatch(sortOrder) {
  return { documents: { sort_order: sortOrder } };
}

export function buildRecentImportWindowPatch(hours) {
  return { documents: { recent_import_window_hours: Number(hours) } };
}

export function buildTrashRetentionPatch(days) {
  return { documents: { trash_retention_days: Number(days) } };
}

export function buildOcrDocLangPatch(lang) {
  return { documents: { ocr_doc_lang: String(lang) } };
}

export function buildOcrEnginePatch(engine) {
  return { ocr: { engine: String(engine) } };
}

export function buildOcrDpiTargetPatch(dpi) {
  return { ocr: { dpi_target: Number(dpi) } };
}

export function buildOcrEnableLayoutPatch(enabled) {
  return { ocr: { enable_layout: Boolean(enabled) } };
}

export function buildOcrEnableTableDetectionPatch(enabled) {
  return { ocr: { enable_table_detection: Boolean(enabled) } };
}

export function buildOcrDeskewPatch(enabled) {
  return { ocr: { deskew: Boolean(enabled) } };
}

export function buildOcrDenoisePatch(enabled) {
  return { ocr: { denoise: Boolean(enabled) } };
}

export function buildOcrUseUnpaperPatch(enabled) {
  return { ocr: { use_unpaper: Boolean(enabled) } };
}

export function buildOcrPostprocessHyphenationPatch(enabled) {
  return { ocr: { postprocess_hyphenation: Boolean(enabled) } };
}

export function buildOcrRemoveHeadersFootersPatch(enabled) {
  return { ocr: { remove_headers_footers: Boolean(enabled) } };
}
