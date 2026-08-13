import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

import {
  addDossierDocuments,
  createDossier,
  createDossierGroup,
  createDossierItem,
  deleteDossier,
  deleteDossierGroup,
  deleteDossierItem,
  deleteDossierItems,
  duplicateDossier,
  getDossierBoard,
  listDossiers,
  patchDossier,
  patchDossierGroup,
  patchDossierItem,
  reorderDossierGroups,
  reorderDossierItems,
  restoreDossierItems,
  uploadDossierImage,
} from '../api/dossiers.js';

function restoreSnapshot(item) {
  return {
    id: item.id,
    item_type: item.item_type,
    group_id: item.group_id ?? null,
    sort_order: Number(item.sort_order || 0),
    pos_x: item.pos_x ?? null,
    pos_y: item.pos_y ?? null,
    document_id: item.document_id ?? null,
    attached_to_item_id: item.attached_to_item_id ?? null,
    note_title: item.note_title ?? null,
    note_body: item.note_body ?? null,
    note_color: item.note_color ?? null,
    link_title: item.link_title ?? null,
    link_url: item.link_url ?? null,
    link_description: item.link_description ?? null,
    image_filename: item.image_filename ?? null,
    image_content_type: item.image_content_type ?? null,
    image_file_key: item.image_file_key ?? null,
    image_size_bytes: item.image_size_bytes ?? null,
    image_width: item.image_width ?? null,
    image_height: item.image_height ?? null,
  };
}

export const useDossierStore = defineStore('dossiers', () => {
  const dossiers = ref([]);
  const currentDossier = ref(null);
  const groups = ref([]);
  const items = ref([]);
  const loading = ref(false);
  const saving = ref(false);
  // Wird nach dem ersten erfolgreichen Laden der Liste dauerhaft true. Erlaubt der
  // Übersicht, echten Leerzustand vs. „noch nicht geladen" zu unterscheiden und so
  // ein Aufblitzen von Skeleton/Leerzustand beim Bereichswechsel zu vermeiden.
  const listLoaded = ref(false);

  const documentItems = computed(() => items.value.filter((item) => item.item_type === 'document'));

  function updateListCounts(dossierId, changes) {
    const index = dossiers.value.findIndex((item) => item.id === dossierId);
    if (index < 0) return;
    const current = dossiers.value[index];
    dossiers.value[index] = {
      ...current,
      ...Object.fromEntries(Object.entries(changes).map(([key, delta]) => [key, Math.max(0, Number(current[key] || 0) + delta)])),
    };
  }

  async function fetchList(options = {}) {
    loading.value = true;
    try {
      const payload = await listDossiers(options);
      dossiers.value = payload?.items || [];
      listLoaded.value = true;
      return dossiers.value;
    } finally {
      loading.value = false;
    }
  }

  async function fetchBoard(dossierId) {
    loading.value = true;
    try {
      const payload = await getDossierBoard(dossierId);
      currentDossier.value = payload.dossier;
      groups.value = payload.groups || [];
      items.value = payload.items || [];
      const index = dossiers.value.findIndex((item) => item.id === dossierId);
      if (index >= 0) {
        dossiers.value[index] = {
          ...dossiers.value[index],
          ...payload.dossier,
          document_count: items.value.filter((item) => item.item_type === 'document').length,
          image_count: items.value.filter((item) => item.item_type === 'image').length,
          item_count: items.value.length,
          group_count: groups.value.length,
        };
      }
      return payload;
    } finally {
      loading.value = false;
    }
  }

  async function add(payload) {
    saving.value = true;
    try {
      const created = await createDossier(payload);
      dossiers.value.unshift({ ...created, document_count: 0, image_count: 0, item_count: 0, group_count: 0 });
      return created;
    } finally {
      saving.value = false;
    }
  }

  async function update(dossierId, payload) {
    saving.value = true;
    try {
      const updated = await patchDossier(dossierId, payload);
      if (currentDossier.value?.id === dossierId) currentDossier.value = updated;
      const index = dossiers.value.findIndex((item) => item.id === dossierId);
      if (index >= 0) dossiers.value[index] = { ...dossiers.value[index], ...updated };
      return updated;
    } finally {
      saving.value = false;
    }
  }

  async function remove(dossierId) {
    await deleteDossier(dossierId);
    dossiers.value = dossiers.value.filter((item) => item.id !== dossierId);
    if (currentDossier.value?.id === dossierId) {
      currentDossier.value = null;
      groups.value = [];
      items.value = [];
    }
  }

  async function duplicate(dossierId) {
    saving.value = true;
    try {
      const source = dossiers.value.find((item) => item.id === dossierId);
      const created = await duplicateDossier(dossierId);
      dossiers.value.unshift({
        ...(source || {}),
        ...created,
        is_favorite: false,
        archived_at: null,
      });
      return created;
    } finally {
      saving.value = false;
    }
  }

  async function setFavorite(dossierId, isFavorite) {
    const listIndex = dossiers.value.findIndex((item) => item.id === dossierId);
    const previousListItem = listIndex >= 0 ? dossiers.value[listIndex] : null;
    const previousCurrent = currentDossier.value?.id === dossierId ? currentDossier.value : null;
    if (listIndex >= 0) {
      dossiers.value[listIndex] = { ...dossiers.value[listIndex], is_favorite: isFavorite };
    }
    if (previousCurrent) currentDossier.value = { ...previousCurrent, is_favorite: isFavorite };
    try {
      const updated = await patchDossier(dossierId, { is_favorite: isFavorite });
      if (listIndex >= 0) dossiers.value[listIndex] = { ...dossiers.value[listIndex], ...updated };
      if (currentDossier.value?.id === dossierId) currentDossier.value = updated;
      return updated;
    } catch (error) {
      if (listIndex >= 0 && previousListItem) dossiers.value[listIndex] = previousListItem;
      if (previousCurrent) currentDossier.value = previousCurrent;
      throw error;
    }
  }

  async function addGroup(dossierId, payload) {
    const created = await createDossierGroup(dossierId, payload);
    groups.value.push(created);
    updateListCounts(dossierId, { group_count: 1 });
    return created;
  }

  async function updateGroup(dossierId, groupId, payload) {
    const updated = await patchDossierGroup(dossierId, groupId, payload);
    const index = groups.value.findIndex((group) => group.id === groupId);
    if (index >= 0) groups.value[index] = updated;
    return updated;
  }

  async function setGroupOrder(dossierId, orderedGroups) {
    const previous = groups.value;
    groups.value = orderedGroups.map((group, index) => ({ ...group, sort_order: (index + 1) * 1000 }));
    try {
      groups.value = await reorderDossierGroups(dossierId, groups.value.map((group) => group.id));
    } catch (error) {
      groups.value = previous;
      throw error;
    }
  }

  async function removeGroup(dossierId, groupId) {
    await deleteDossierGroup(dossierId, groupId);
    groups.value = groups.value.filter((group) => group.id !== groupId);
    items.value = items.value.map((item) => item.group_id === groupId ? { ...item, group_id: null } : item);
    updateListCounts(dossierId, { group_count: -1 });
  }

  async function addDocuments(dossierId, documentIds, groupId = null) {
    const payload = await addDossierDocuments(dossierId, documentIds, groupId);
    items.value.push(...(payload.items || []));
    const added = payload.items?.length || 0;
    updateListCounts(dossierId, { document_count: added, item_count: added });
    return payload;
  }

  async function addItem(dossierId, payload) {
    const created = await createDossierItem(dossierId, payload);
    items.value.push(created);
    updateListCounts(dossierId, {
      item_count: 1,
      document_count: created.item_type === 'document' ? 1 : 0,
      image_count: created.item_type === 'image' ? 1 : 0,
    });
    return created;
  }

  async function addImage(dossierId, file) {
    const created = await uploadDossierImage(dossierId, file);
    items.value.push(created);
    updateListCounts(dossierId, { item_count: 1, image_count: 1 });
    return created;
  }

  async function updateItem(dossierId, itemId, payload) {
    const updated = await patchDossierItem(dossierId, itemId, payload);
    const index = items.value.findIndex((item) => item.id === itemId);
    if (index >= 0) items.value[index] = updated;
    return updated;
  }

  async function setItemPlacements(dossierId, placements) {
    const previous = items.value.map((item) => ({ ...item }));
    const placementMap = new Map(placements.map((placement) => [placement.item_id, placement]));
    items.value = items.value.map((item) => {
      const placement = placementMap.get(item.id);
      return placement
        ? {
            ...item,
            group_id: placement.group_id,
            sort_order: placement.sort_order,
            pos_x: placement.pos_x ?? null,
            pos_y: placement.pos_y ?? null,
          }
        : item;
    });
    try {
      const updated = await reorderDossierItems(dossierId, placements);
      const updatedMap = new Map(updated.map((item) => [item.id, item]));
      items.value = items.value.map((item) => updatedMap.get(item.id) || item);
      return updated;
    } catch (error) {
      items.value = previous;
      throw error;
    }
  }

  async function removeItem(dossierId, itemId) {
    const removed = items.value.find((item) => item.id === itemId);
    await deleteDossierItem(dossierId, itemId);
    items.value = items.value
      .filter((item) => item.id !== itemId)
      .map((item) => item.attached_to_item_id === itemId
        ? { ...item, attached_to_item_id: null }
        : item);
    updateListCounts(dossierId, {
      item_count: -1,
      document_count: removed?.item_type === 'document' ? -1 : 0,
      image_count: removed?.item_type === 'image' ? -1 : 0,
    });
  }

  async function removeItems(dossierId, itemIds) {
    const uniqueIds = [...new Set(itemIds)];
    const removeSet = new Set(uniqueIds);
    const removed = items.value.filter((item) => removeSet.has(item.id));
    if (removed.length !== uniqueIds.length) throw new Error('Mindestens ein Leuchttisch-Element wurde nicht gefunden.');
    await deleteDossierItems(dossierId, uniqueIds);
    items.value = items.value
      .filter((item) => !removeSet.has(item.id))
      .map((item) => removeSet.has(item.attached_to_item_id)
        ? { ...item, attached_to_item_id: null }
        : item);
    updateListCounts(dossierId, {
      item_count: -removed.length,
      document_count: -removed.filter((item) => item.item_type === 'document').length,
      image_count: -removed.filter((item) => item.item_type === 'image').length,
    });
    return removed;
  }

  async function restoreItems(dossierId, snapshots) {
    const payload = await restoreDossierItems(dossierId, snapshots.map(restoreSnapshot));
    const restored = payload.items || [];
    const restoredIds = new Set(restored.map((item) => item.id));
    items.value = [
      ...items.value.filter((item) => !restoredIds.has(item.id)),
      ...restored,
    ].sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0));
    updateListCounts(dossierId, {
      item_count: restored.length,
      document_count: restored.filter((item) => item.item_type === 'document').length,
      image_count: restored.filter((item) => item.item_type === 'image').length,
    });
    return restored;
  }

  return {
    dossiers,
    currentDossier,
    groups,
    items,
    documentItems,
    loading,
    saving,
    listLoaded,
    fetchList,
    fetchBoard,
    add,
    update,
    remove,
    duplicate,
    setFavorite,
    addGroup,
    updateGroup,
    setGroupOrder,
    removeGroup,
    addDocuments,
    addItem,
    addImage,
    updateItem,
    setItemPlacements,
    removeItem,
    removeItems,
    restoreItems,
  };
});
