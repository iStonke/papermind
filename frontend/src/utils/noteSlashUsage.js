export const NOTE_SLASH_USAGE_STORAGE_KEY = 'pm-note-slash-command-usage-v1';

export const DEFAULT_FREQUENT_SLASH_COMMAND_KEYS = Object.freeze([
  'h2',
  'ul',
  'task',
  'callout-important',
  'beleg',
]);

export function parseNoteSlashUsage(rawValue) {
  if (!rawValue) return {};
  try {
    const parsed = typeof rawValue === 'string' ? JSON.parse(rawValue) : rawValue;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([key, count]) => (
        typeof key === 'string'
        && key.length > 0
        && Number.isSafeInteger(count)
        && count > 0
      )),
    );
  } catch {
    return {};
  }
}
export function incrementNoteSlashUsage(usage, commandKey) {
  const key = String(commandKey || '').trim();
  if (!key) return parseNoteSlashUsage(usage);
  const normalized = parseNoteSlashUsage(usage);
  return {
    ...normalized,
    [key]: Math.min(Number.MAX_SAFE_INTEGER, (normalized[key] || 0) + 1),
  };
}

export function mostUsedSlashCommands(
  commands,
  usage,
  { limit = 5, defaults = DEFAULT_FREQUENT_SLASH_COMMAND_KEYS } = {},
) {
  const normalizedUsage = parseNoteSlashUsage(usage);
  const defaultOrder = new Map(defaults.map((key, index) => [key, index]));
  const originalOrder = new Map(commands.map((command, index) => [command.key, index]));
  const fallbackRank = (command) => (
    defaultOrder.has(command.key)
      ? defaultOrder.get(command.key)
      : defaults.length + (originalOrder.get(command.key) || 0)
  );

  return [...commands]
    .sort((left, right) => (
      (normalizedUsage[right.key] || 0) - (normalizedUsage[left.key] || 0)
      || fallbackRank(left) - fallbackRank(right)
    ))
    .slice(0, Math.max(0, Number(limit) || 0));
}
