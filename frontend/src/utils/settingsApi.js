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

export function buildDrawerAlwaysExpandedPatch(enabled) {
  return { ui: { drawerAlwaysExpanded: Boolean(enabled) } };
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
