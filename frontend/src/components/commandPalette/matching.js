/**
 * Reine, DOM-freie Logik der Command-Palette – bewusst ausgelagert, damit sie
 * ohne Vue/Browser per node:test geprüft werden kann: Prefix-Parsing,
 * Fuzzy-Match mit Treffer-Highlight, Filtern + Gruppieren.
 */

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/**
 * Trennt einen Präfix-Modus (>, #, @ …) vom Suchbegriff.
 * @param {string} raw       Rohtext des Eingabefelds
 * @param {Object} modeGroups z. B. { '>': 'action', '#': 'tag', '@': 'correspondent' }
 * @returns {{ mode: string|null, term: string }}
 */
export function parsePrefix(raw, modeGroups = {}) {
  const value = String(raw ?? '');
  const first = value.charAt(0);
  if (modeGroups[first]) return { mode: first, term: value.slice(1).trim() };
  return { mode: null, term: value.trim() };
}

/**
 * Subsequenz-Match aufs Label mit <mark>-Hervorhebung der Treffer; fällt es
 * durch, greift ein einfacher (nicht hervorgehobener) Keyword-Treffer.
 * @returns {{ ok: boolean, html?: string }}
 */
export function matchEntry(entry, term) {
  const label = String(entry.label);
  const needle = String(term).toLowerCase();
  const lc = label.toLowerCase();
  let ti = 0;
  let out = '';
  for (let i = 0; i < label.length; i += 1) {
    if (ti < needle.length && lc[i] === needle[ti]) {
      out += `<mark>${escapeHtml(label[i])}</mark>`;
      ti += 1;
    } else {
      out += escapeHtml(label[i]);
    }
  }
  if (ti === needle.length) return { ok: true, html: out };
  if (entry.keywords?.some((k) => String(k).toLowerCase().includes(needle))) {
    return { ok: true, html: escapeHtml(label) };
  }
  return { ok: false };
}

/**
 * Filtert die Einträge (optional auf eine Gruppe beschränkt) und sortiert die
 * Treffer in die vorgegebene Gruppenreihenfolge. Jedem sichtbaren Eintrag wird
 * ein fortlaufender flacher Index (für Tastaturnavigation) zugewiesen.
 *
 * @param {Array}  entries    Einträge mit { group, label, keywords? }
 * @param {Object} opts
 * @param {string} opts.term         Suchbegriff ('' = alles zeigen)
 * @param {string|null} opts.restrictGroup Nur diese Gruppe zulassen (Präfix-Modus)
 * @param {Array}  opts.groupOrder   [{ key, label, limit? }]
 * @returns {Array} [{ key, label, items: [{ entry, html, index }] }]
 */
export function buildGroups(entries, { term = '', restrictGroup = null, groupOrder = [] } = {}) {
  const hasTerm = String(term).trim().length > 0;
  const byGroup = {};
  for (const entry of entries) {
    if (restrictGroup && entry.group !== restrictGroup) continue;
    let html;
    if (!hasTerm) {
      html = escapeHtml(entry.label);
    } else {
      const m = matchEntry(entry, term);
      if (!m.ok) continue;
      html = m.html;
    }
    (byGroup[entry.group] ||= []).push({ entry, html });
  }

  let index = 0;
  const groups = [];
  for (const cfg of groupOrder) {
    let items = byGroup[cfg.key];
    if (!items?.length) continue;
    if (cfg.limit != null) items = items.slice(0, cfg.limit);
    groups.push({
      key: cfg.key,
      label: cfg.label,
      items: items.map((it) => ({ ...it, index: index++ })),
    });
  }
  return groups;
}
