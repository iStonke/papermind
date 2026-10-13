/** Accept untouched rows from a reload while preserving newer writes/deletions. */
export function reconcileRecordReload(current, incoming, versions, requestedVersion) {
  const byId = new Map(current.map(item => [item.id, item]));
  const received = new Set(incoming.map(item => item.id));
  const newer = id => (versions.get(id) || 0) > requestedVersion;
  const result = incoming.flatMap(item => {
    if (!newer(item.id)) return [item];
    return byId.has(item.id) ? [byId.get(item.id)] : [];
  });
  for (const item of current) {
    if (newer(item.id) && !received.has(item.id)) result.push(item);
  }
  return result;
}
