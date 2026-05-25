export function buildThemeModePatch(themeMode) {
  return { ui: { theme_mode: themeMode } };
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

export function buildSortOrderPatch(sortOrder) {
  return { documents: { sort_order: sortOrder } };
}

export function buildRecentImportWindowPatch(hours) {
  return { documents: { recent_import_window_hours: Number(hours) } };
}

export function buildTrashRetentionPatch(days) {
  return { documents: { trash_retention_days: Number(days) } };
}
