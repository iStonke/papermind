<template>
  <section class="thoughts-ws" :class="{ 'is-list-collapsed': listHidden }" aria-label="Gedanken">
    <aside id="thoughts-list-panel" class="thoughts-inbox" aria-label="Gedankeneingang" :inert="listHidden" :aria-hidden="listHidden ? 'true' : undefined">
      <header class="thoughts-header" :class="{ 'thoughts-header--search-focused': searchFocused }">
        <div class="thoughts-heading"><h1>Gedanken</h1></div>
        <div class="pm-searchbar pm-searchbar--header" :class="{ 'pm-searchbar--filled': !!query, 'pm-searchbar--scoped': searchScope !== 'all' }" role="search" @focusin="searchFocused = true" @focusout="searchFocused = $event.currentTarget.contains($event.relatedTarget)">
          <v-text-field v-model="query" class="pm-searchbar__field" prepend-inner-icon="mdi-magnify" clearable placeholder="Suchen …" aria-label="Gedanken durchsuchen" density="compact" variant="plain" hide-details />
          <span class="pm-searchbar__divider" aria-hidden="true" />
          <v-menu location="bottom end" offset="6">
            <template #activator="{ props: menuProps }"><button v-bind="menuProps" type="button" class="pm-searchbar__scope" :aria-label="`Suchfeld: ${searchScopeLabel}`" :title="`Suchen in: ${searchScopeLabel}`"><v-icon size="15" class="pm-searchbar__scope-icon">mdi-file-search-outline</v-icon><span class="pm-searchbar__scope-label">{{ searchScopeLabel }}</span><v-icon size="14" class="pm-searchbar__scope-chevron">mdi-chevron-down</v-icon></button></template>
            <v-list class="pm-menu pm-searchbar__menu" density="compact"><v-list-subheader>Suchen in</v-list-subheader><v-list-item v-for="option in searchScopes" :key="option.value" :title="option.label" :active="searchScope === option.value" @click="searchScope = option.value"><template v-if="searchScope === option.value" #append><v-icon size="16">mdi-check</v-icon></template></v-list-item></v-list>
          </v-menu>
        </div>
      </header>
      <ListActionToolbar :actions="sortActions" :show-selection="false" @action-select="changeSort" />
      <div v-if="error" class="thoughts-error" role="alert">{{ error }} <button type="button" @click="load">Neu laden</button></div>
      <div class="thoughts-list document-list-shell" :aria-busy="loading">
        <div class="document-list-body"><div class="document-list-content">
          <p v-if="loading && !rooms.length" class="thoughts-muted" role="status">Gedanken werden geladen …</p>
          <div v-else-if="!visibleRooms.length" class="thoughts-list-empty">
            <PmEmptyState
              icon="mdi-thought-bubble-outline"
              :title="query ? 'Keine passenden Sammlungen' : 'Noch keine Sammlungen'"
              :subtitle="query ? 'Passe den Suchbegriff an oder leere die Suche.' : 'Lege deine erste Sammlung an, um Gedanken zu ordnen.'"
              size="md"
            />
          </div>
          <div v-else class="notes-ws__groups"><section class="notes-ws__group notes-ws__group--flat"><ul class="notes-ws__list">
            <li v-for="room in visibleRooms" :key="room.id" class="notes-ws__item" :data-room-id="room.id" :class="{ 'is-active': activeRoomId === room.id, 'is-new': newlyCreatedRoomId === room.id }" @animationend.self="finishNewRoomAnimation(room.id)">
              <button type="button" class="notes-ws__item-select" :aria-current="activeRoomId === room.id ? 'true' : undefined" :disabled="saving" @click="selectRoom(room.id)">
                <span class="notes-ws__item-head"><span class="notes-ws__item-title">{{ room.title }}</span></span>
                <span class="notes-ws__item-snippet">{{ room.content?.trim().replace(/\s+/g, ' ') || 'Platz für deine Gedanken' }}</span>
                <span class="thoughts-room-meta"><span>{{ room.note_count || 0 }} {{ (room.note_count || 0) === 1 ? 'Gedanke' : 'Gedanken' }}</span><span aria-hidden="true">·</span><span>{{ listDateLabel(room.updated_at) }}</span></span>
              </button>
              <button type="button" class="notes-ws__item-delete" title="Sammlung löschen" aria-label="Sammlung löschen" :disabled="saving" @click="error = ''; deleteRoomTarget = room"><v-icon size="16">mdi-trash-can-outline</v-icon></button>
              <button type="button" class="notes-ws__item-pin thoughts-item-edit" title="Sammlung umbenennen" aria-label="Sammlung umbenennen" :disabled="saving" @click="openRoomDialog(room)"><v-icon size="16">mdi-pencil-outline</v-icon></button>
            </li>
          </ul></section></div>
        </div></div>
      </div>
      <div v-if="!error" class="notes-ws__fab"><v-btn class="notes-ws__fab-main" :class="{ 'is-click-animated': fabClickAnimating }" color="primary" :loading="creatingRoom" :disabled="loading || saving || !activeCollectionId" @click="createRoomFromFab" @animationend.self="fabClickAnimating = false"><v-icon size="20" class="mr-1">mdi-square-edit-outline</v-icon>Neue Sammlung</v-btn></div>
    </aside>
    <button v-if="!compactLayout" type="button" class="thoughts-list-handle" :aria-label="listHidden ? 'Gedankenliste einblenden' : 'Gedankenliste ausblenden'" :title="listHidden ? 'Gedankenliste einblenden' : 'Gedankenliste ausblenden'" :aria-pressed="!listHidden" aria-controls="thoughts-list-panel" @click="toggleThoughtsList"><v-icon size="18" aria-hidden="true">{{ listHidden ? 'mdi-chevron-right' : 'mdi-chevron-left' }}</v-icon></button>
    <main ref="boardElement" class="thoughts-board" aria-label="Gedankensammlung">
      <div v-if="showThoughtsEmptyState" class="thoughts-board-empty thoughts-board-empty--visual">
        <div class="thoughts-empty-visual" aria-hidden="true">
          <span class="thoughts-empty-card thoughts-empty-card--one"><i></i><b></b><b></b></span>
          <span class="thoughts-empty-card thoughts-empty-card--two"><i></i><b></b><b></b></span>
          <span class="thoughts-empty-spark thoughts-empty-spark--one">✦</span>
          <span class="thoughts-empty-spark thoughts-empty-spark--two">✦</span>
          <span class="thoughts-empty-plus"><v-icon size="22">mdi-plus</v-icon></span>
        </div>
        <div class="thoughts-empty-copy">
          <h2>{{ activeRoomId ? 'Dein erster Gedanke wartet' : 'Deine erste Sammlung wartet' }}</h2>
          <p>{{ activeRoomId ? 'Halte eine Idee fest. Du kannst sie anschließend frei auf der Fläche anordnen.' : 'Lege eine Sammlung an und halte darin Ideen, Fragen und Notizen fest.' }}</p>
          <button
            type="button"
            class="thoughts-empty-action"
            :disabled="saving || loading || !activeCollectionId"
            @click="activeRoomId ? createFromButton() : createRoomFromFab()"
          >
            <v-icon size="18">{{ activeRoomId ? 'mdi-square-edit-outline' : 'mdi-plus' }}</v-icon>
            <span>{{ activeRoomId ? 'Ersten Gedanken festhalten' : 'Erste Sammlung anlegen' }}</span>
          </button>
        </div>
      </div>
      <p v-else-if="archived && !loading && !pins.length && !error" class="thoughts-board-empty"><v-icon size="44">mdi-thought-bubble-outline</v-icon><span>Noch keine archivierten Gedanken</span></p>
      <div ref="canvas" class="thoughts-canvas" :style="canvasStyle" aria-label="Arbeitsbereich der Gedankensammlung" @pointerdown.self="startSelection" @click.self="clearCanvasSelection" @dblclick.self.prevent="createAtClick">
        <div v-if="selectionBox" class="thoughts-selection-box" :style="{ left:`${selectionBox.x}px`, top:`${selectionBox.y}px`, width:`${selectionBox.width}px`, height:`${selectionBox.height}px` }" />
        <Transition name="thought-dismiss" :css="!saving && !switchingRoom">
        <form v-if="!archived && draftPosition" :key="draftGeneration" class="thoughts-card thoughts-capture thoughts-card--growing" :style="draftStyle" aria-label="Neuer Gedanke" @submit.prevent="capture">
          <header><div class="thoughts-card-meta"><time :datetime="draftPosition.created_at">{{ dateLabel(draftPosition.created_at) }}</time></div><ThoughtColorPicker :model-value="draftPosition.title_color || '#cce0dc'" :disabled="saving" @update:model-value="draftPosition = { ...draftPosition, title_color: $event }" /><button type="button" :disabled="saving" :aria-label="draft.trim() ? 'Gedanken speichern und schließen' : 'Leeren Gedanken schließen'" @click="closeDraft"><v-icon size="17">mdi-close</v-icon></button></header>
          <textarea ref="captureInput" v-model="draft" aria-label="Gedanken festhalten" placeholder="Dein Gedanke …" maxlength="20000" :disabled="saving || loading || !activeCollectionId || editingId !== null" @input="resizeTextArea($event.target)" @blur="captureOnBlur" @keydown="captureShortcut" />
        </form>
        </Transition>
        <TransitionGroup name="thought-dismiss" :css="!switchingRoom">
        <article v-for="pin in visiblePins" :id="`thought-${pin.id}`" :key="pin.id" class="thoughts-card" :style="cardStyle(pin)" :class="{ 'is-active': activeId === pin.id, 'is-selected': selectedPinIds.includes(pin.id) }" tabindex="-1" @click.capture="modifiedCardSelection($event, pin)">
          <header class="thoughts-titlebar" role="group" :tabindex="saving || editingId !== null ? -1 : 0" aria-label="Gedanken verschieben" title="Titelleiste ziehen zum Verschieben · Pfeiltasten bewegen" :class="{ 'is-disabled': saving || editingId !== null }" @pointerdown="startDrag($event, pin)" @keydown="moveWithKeys($event, pin)"><div class="thoughts-card-meta"><time :datetime="pin.created_at">{{ dateLabel(pin.created_at) }}</time></div><ThoughtColorPicker :model-value="pin.title_color || '#cce0dc'" :disabled="saving || editingId !== null" @update:model-value="setTitleColor(pin, $event)" /><button v-if="!archived" type="button" title="Gedanken entfernen" aria-label="Gedanken entfernen" :disabled="saving || editingId !== null" @click.stop="archiveItems([pin.id])"><v-icon size="17">mdi-close</v-icon></button></header>
          <form v-if="editingId === pin.id" @submit.prevent="saveEdit(pin)">
            <textarea v-model="editText" class="thoughts-edit" aria-label="Gedanken bearbeiten" maxlength="20000" @input="resizeTextArea($event.target)" @blur="saveEdit(pin)" @keydown.meta.enter.prevent="saveEdit(pin)" @keydown.ctrl.enter.prevent="saveEdit(pin)" />
          </form>
          <textarea v-else v-auto-height class="thoughts-text thoughts-text--editable" :value="pin.text" readonly aria-label="Gedankentext direkt bearbeiten" @click="editPin(pin, $event)" @keydown.enter.prevent="editPin(pin)" @keydown.space.prevent="editPin(pin)" />
          <div v-if="pin.tags?.length" class="thoughts-tags"><button v-for="tag in pin.tags" :key="tag.id" type="button" @click="query = '#' + tag.name">#{{ tag.name }}</button></div>
          <footer v-if="archived && editingId !== pin.id"><button type="button" :disabled="saving || editingId !== null" @click="archiveItems([pin.id])"><v-icon size="15">mdi-archive-arrow-up-outline</v-icon>Zurückholen</button></footer>
        </article>
        </TransitionGroup>
      </div>
    </main>
    <div class="thoughts-toolbar" role="toolbar" aria-label="Gedankenwerkzeuge">
      <button type="button" title="Neuer Gedanke" aria-label="Neuer Gedanke" :disabled="saving || loading" @click="createFromButton"><v-icon size="22">mdi-square-edit-outline</v-icon></button>
      <ThoughtColorPicker :model-value="toolbarColor" :disabled="saving || editingId !== null || selectionBusy || !selectedPinIds.length" @update:model-value="chooseToolbarColor" />
      <button type="button" class="thoughts-delete-selected" title="Ausgewählte Gedanken löschen" aria-label="Ausgewählte Gedanken löschen" :disabled="saving || selectionBusy || editingId !== null || !selectedPinIds.length" @click="deleteSelectedPins"><v-icon size="22">mdi-trash-can-outline</v-icon></button>
      <span class="thoughts-toolbar-divider" aria-hidden="true" />
      <button type="button" title="Alle Gedanken anzeigen" aria-label="Alle Gedanken anzeigen" :disabled="!visiblePins.length" @click="fitThoughts"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><rect x="8" y="8" width="8" height="8" rx="1"/></svg></button>
      <button type="button" title="Gedanken in der Sammlung ordnen" aria-label="Gedanken ordnen" :disabled="saving || editingId !== null || draftPosition !== null || !visiblePins.length" @click="arrangeThoughts"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></button>
      <span class="thoughts-toolbar-divider" aria-hidden="true" />
      <button type="button" title="Alle Gedanken zusammenfassen" aria-label="Alle Gedanken zusammenfassen" :disabled="saving || loading || switchingRoom || summaryGenerating || !visiblePins.length" @click="openSummary"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/><path d="m20 2 .7 2.3L23 5l-2.3.7L20 8l-.7-2.3L17 5l2.3-.7Z"/></svg></button>
      <span class="thoughts-toolbar-divider" aria-hidden="true" />
      <button type="button" title="Entfernen rückgängig machen" aria-label="Entfernen rückgängig machen" :disabled="saving || editingId !== null || !undoIds.length" @click="undoArchive"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5 4 10l5 5M4 10h10a6 6 0 0 1 0 12" transform="translate(0 -2)" /></svg></button>
    </div>
    <div class="thoughts-zoom" role="group" aria-label="Zoom der Gedankensammlung">
      <button type="button" aria-label="Verkleinern" :disabled="zoom <= .1" @click="changeZoom(-.1)">−</button>
      <button type="button" aria-label="Zoom auf 100 Prozent zurücksetzen" title="Auf 100 % zurücksetzen" @click="setCanvasZoom(1)">{{ Math.round(zoom * 100) }} %</button>
      <button type="button" aria-label="Vergrößern" :disabled="zoom >= 2" @click="changeZoom(.1)">+</button>
    </div>
    <BaseDialog
      v-model="summaryDialog"
      title="Gedanken zusammenfassen"
      :header-subtitle="`Alle Gedanken aus „${summaryRoomTitle}“ als neue Notiz ausarbeiten.`"
      icon="mdi-note-outline"
      :max-width="600"
      primary-text="Als Notiz übernehmen"
      secondary-text="Zurück"
      :loading="summaryTransferring"
      :persistent="summaryTransferring"
      :primary-disabled="summaryGenerating || !!summaryNoteId || !summaryTitle.trim() || !summaryContent.trim()"
      @primary="transferSummary"
      @close="cancelSummaryGeneration"
    >
      <div v-if="summaryGenerating" class="thoughts-summary-progress" role="status"><v-progress-linear indeterminate color="primary" rounded /><p>Die Gedanken werden zusammengefasst und sinnvoll ergänzt …</p></div>
      <template v-else>
        <v-text-field v-model="summaryTitle" label="Titel der neuen Notiz" maxlength="500" density="comfortable" variant="outlined" :disabled="summaryTransferring" />
        <v-textarea v-model="summaryContent" label="Zusammenfassung" rows="8" auto-grow max-rows="14" maxlength="30000" density="comfortable" variant="outlined" hide-details :disabled="summaryTransferring" />
        <p class="thoughts-summary-hint">Titel und Text sind editierbar. Erst „Als Notiz übernehmen“ legt die Notiz an.</p>
      </template>
      <div v-if="summaryError" class="thoughts-dialog-error" role="alert">{{ summaryError }}<v-btn v-if="!summaryContent && !summaryGenerating" variant="text" size="small" @click="generateSummary">Erneut versuchen</v-btn></div>
    </BaseDialog>
    <BaseDialog
      v-model="roomDialog"
      title="Sammlung umbenennen"
      header-subtitle="Wie soll diese Sammlung heißen?"
      primary-text="Speichern"
      secondary-text="Zurück"
      icon="mdi-pencil-outline"
      :max-width="480"
      :loading="saving"
      :persistent="saving"
      :primary-disabled="!roomName.trim()"
      @primary="saveRoom"
    >
      <v-text-field v-model="roomName" label="Name" maxlength="120" density="comfortable" variant="outlined" hide-details autofocus :disabled="saving" @keydown.enter.prevent="saveRoom" />
      <p v-if="error" class="thoughts-dialog-error" role="alert">{{ error }}</p>
    </BaseDialog>
    <DestructiveDialog
      :model-value="!!deleteRoomTarget"
      title="Sammlung löschen"
      header-subtitle="Möchtest du diese Sammlung und alle Gedanken darin endgültig löschen?"
      primary-text="Löschen"
      secondary-text="Zurück"
      icon="mdi-trash-can-outline"
      :max-width="480"
      :loading="saving"
      :persistent="saving"
      @update:model-value="!$event && !saving && (deleteRoomTarget = null)"
      @primary="removeRoom"
      @close="!saving && (deleteRoomTarget = null)"
    >
      <p class="thoughts-dialog-name">„{{ deleteRoomTarget?.title }}“</p>
      <p v-if="error" class="thoughts-dialog-error" role="alert">{{ error }}</p>
    </DestructiveDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import BaseDialog from '../components/BaseDialog.vue';
import DestructiveDialog from '../components/DestructiveDialog.vue';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import PmEmptyState from '../components/PmEmptyState.vue';
import { resizeThoughtText as resizeTextArea } from '../utils/thoughtTextSize.js';
import { shiftedThoughtPositions } from '../utils/thoughtGroupMove.js';
import { selectionRect, intersectingThoughtIds } from '../utils/thoughtSelection.js';
import { findFreeThoughtPosition, THOUGHT_PLACEMENT_GAP } from '../utils/thoughtPlacement.js';
import { noteMarkdownToTipTap } from '../utils/noteMarkdown.js';
import { sortThoughts } from '../utils/thoughtSort.js';
import ThoughtColorPicker from '../components/ThoughtColorPicker.vue';
import { storeToRefs } from 'pinia';
import { useNotesStore } from '../stores/notes.js';
import { useAuthStore } from '../stores/auth.js';
import { listPins, createPin, updatePin, archivePins, movePin, listThoughtRooms, createThoughtRoom, renameThoughtRoom, deleteThoughtRoom, colorPins, movePins, summarizeThoughtRoom } from '../api/notes.js';
import { mapApiError } from '../stores/notifications.js';

const defaultTitleColor = ref('#cce0dc');
const zoom = ref(1), boardElement = ref(null);
let gestureZoom = null, touchZoom = null, rawGestureZoom = null, wheelSnapTimer = null;
function changeZoom(step) { setCanvasZoom(Math.round((zoom.value + step) * 10) / 10); }
function snapGestureZoom(value) {
  return Math.abs(value - 1) <= .035 ? 1 : value;
}
function setCanvasZoom(value, point = null) {
  if (!Number.isFinite(value)) return;
  const next = Math.max(.1, Math.min(2, value));
  if (Math.abs(next - zoom.value) < .0001) return;
  const board = boardElement.value, surface = canvas.value;
  if (!board || !surface) { zoom.value = next; return; }
  const rect = board.getBoundingClientRect(), before = surface.getBoundingClientRect();
  const x = Number.isFinite(point?.clientX) ? point.clientX : rect.left + board.clientWidth / 2;
  const y = Number.isFinite(point?.clientY) ? point.clientY : rect.top + board.clientHeight / 2;
  const logicalX = (x - before.left) / zoom.value, logicalY = (y - before.top) / zoom.value;
  zoom.value = next;
  nextTick(() => {
    const after = surface.getBoundingClientRect();
    board.scrollLeft += after.left + logicalX * next - x;
    board.scrollTop += after.top + logicalY * next - y;
  });
}
function onCanvasWheel(event) {
  if (!event.ctrlKey && !event.metaKey) return;
  event.preventDefault();
  if (gestureZoom !== null) return;
  const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? boardElement.value.clientHeight : 1);
  if (Number.isFinite(delta) && Math.abs(delta) >= .01) {
    rawGestureZoom = Math.max(.1, Math.min(2, (rawGestureZoom ?? zoom.value) * Math.exp(-delta * .0025)));
    setCanvasZoom(snapGestureZoom(rawGestureZoom), event);
    clearTimeout(wheelSnapTimer);
    wheelSnapTimer = setTimeout(() => { rawGestureZoom = null; }, 180);
  }
}
function gestureStart(event) { event.preventDefault(); cancelSelection(); cancelDrag(); gestureZoom = zoom.value; }
function gestureChange(event) { if (gestureZoom === null) return; event.preventDefault(); setCanvasZoom(snapGestureZoom(gestureZoom * Number(event.scale || 1)), event); }
function gestureEnd(event) { if (gestureZoom === null) return; event.preventDefault(); gestureZoom = null; }
function touchPoint(event) {
  const [a, b] = event.touches;
  return { distance:Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY), clientX:(a.clientX + b.clientX) / 2, clientY:(a.clientY + b.clientY) / 2 };
}
function touchStart(event) {
  if (event.touches.length !== 2) return;
  cancelDrag(); const point = touchPoint(event);
  touchZoom = { distance:point.distance, zoom:zoom.value };
}
function touchMove(event) {
  if (!touchZoom || event.touches.length !== 2) return;
  event.preventDefault();
  if (gestureZoom !== null) return;
  const point = touchPoint(event);
  if (touchZoom.distance > 0) setCanvasZoom(snapGestureZoom(touchZoom.zoom * point.distance / touchZoom.distance), point);
}
function touchEnd(event) { if (event.touches.length < 2) touchZoom = null; }
const zoomListeners = { wheel:onCanvasWheel, gesturestart:gestureStart, gesturechange:gestureChange, gestureend:gestureEnd, touchstart:touchStart, touchmove:touchMove, touchend:touchEnd, touchcancel:touchEnd };
onMounted(() => { for (const [name, handler] of Object.entries(zoomListeners)) boardElement.value.addEventListener(name, handler, { passive:false }); });
onBeforeUnmount(() => { clearTimeout(wheelSnapTimer); for (const [name, handler] of Object.entries(zoomListeners)) boardElement.value?.removeEventListener(name, handler); });
const compactLayout = ref(window.innerWidth <= 650), listCollapsed = ref(false);
try { listCollapsed.value = localStorage.getItem('pm-thoughts-list-collapsed') === 'true'; } catch { /* Optional preference. */ }
const listHidden = computed(() => listCollapsed.value && !compactLayout.value);
function updateCompactLayout() { compactLayout.value = window.innerWidth <= 650; }
function toggleThoughtsList() {
  listCollapsed.value = !listCollapsed.value;
  try { localStorage.setItem('pm-thoughts-list-collapsed', String(listCollapsed.value)); } catch { /* Optional preference. */ }
}
onMounted(() => window.addEventListener('resize', updateCompactLayout));
onBeforeUnmount(() => window.removeEventListener('resize', updateCompactLayout));
const emit = defineEmits(['open-note']);
const summaryDialog = ref(false), summaryGenerating = ref(false), summaryTransferring = ref(false);
const summaryTitle = ref(''), summaryContent = ref(''), summaryError = ref(''), summaryNoteId = ref(null);
const summaryRoomTitle = ref('');
let summaryRoomId = null, summaryCollectionId = null, summaryController = null, summaryVersion = 0;
async function openSummary() {
  if (!activeRoomId.value || !await finishRoomEditing()) return;
  summaryRoomId = activeRoomId.value; summaryCollectionId = activeCollectionId.value;
  summaryRoomTitle.value = rooms.value.find((room) => room.id === summaryRoomId)?.title || 'Sammlung';
  summaryTitle.value = ''; summaryContent.value = ''; summaryError.value = ''; summaryNoteId.value = null;
  summaryDialog.value = true;
  await generateSummary();
}
async function generateSummary() {
  if (summaryGenerating.value || !summaryRoomId) return;
  const version = ++summaryVersion;
  summaryController = new AbortController();
  summaryGenerating.value = true; summaryError.value = '';
  try {
    const result = await summarizeThoughtRoom(summaryRoomId,{ signal:summaryController.signal });
    if (version !== summaryVersion || disposed || !summaryDialog.value) return;
    summaryTitle.value = result.title; summaryContent.value = result.content;
  } catch (exc) {
    if (version === summaryVersion && !disposed && exc.name !== 'AbortError') summaryError.value = mapApiError(exc) || exc.message;
  } finally { if (version === summaryVersion) { summaryGenerating.value = false; summaryController = null; } }
}
function cancelSummaryGeneration() {
  summaryVersion++; summaryController?.abort(); summaryController = null; summaryGenerating.value = false;
}
async function transferSummary() {
  if (summaryTransferring.value || summaryGenerating.value || summaryNoteId.value || !summaryTitle.value.trim() || !summaryContent.value.trim()) return;
  summaryTransferring.value = true; summaryError.value = '';
  try {
    const note = await store.create({ collection_id:summaryCollectionId,title:summaryTitle.value.trim(),body_json:{ type:'doc', content:noteMarkdownToTipTap(summaryContent.value.trim()) } });
    summaryNoteId.value = note.id; summaryDialog.value = false;
    emit('open-note',note.id);
  } catch (exc) { summaryError.value = mapApiError(exc) || exc.message; }
  finally { summaryTransferring.value = false; }
}
onBeforeUnmount(cancelSummaryGeneration);
const creatingRoom = ref(false), fabClickAnimating = ref(false), newlyCreatedRoomId = ref(null);
let newRoomAnimationTimer = null, fabAnimationFrame = null;
function finishNewRoomAnimation(id) {
  if (newlyCreatedRoomId.value !== id) return;
  newlyCreatedRoomId.value = null;
  clearTimeout(newRoomAnimationTimer); newRoomAnimationTimer = null;
}
function createRoomFromFab() {
  if (creatingRoom.value) return;
  fabClickAnimating.value = false;
  fabAnimationFrame = requestAnimationFrame(() => { fabClickAnimating.value = true; });
  createRoomAutomatically();
}
onBeforeUnmount(() => { clearTimeout(newRoomAnimationTimer); if (fabAnimationFrame) cancelAnimationFrame(fabAnimationFrame); });
const switchingRoom = ref(false), deleteRoomTarget = ref(null);
const rooms = ref([]), activeRoomId = ref(null), roomDialog = ref(false), roomName = ref(''), renameRoomId = ref(null);
function openRoomDialog(room = null) { error.value = ''; renameRoomId.value = room?.id || null; roomName.value = room?.title || ''; roomDialog.value = true; }
async function finishRoomEditing() {
  if (selectionBusy.value) return false;
  if (positionRequest) await positionRequest;
  if (saving.value) return false;
  if (editingId.value) { await saveEdit(pins.value.find((pin) => pin.id === editingId.value)); if (editingId.value) return false; }
  if (draft.value.trim()) { await capture(); if (draft.value.trim()) return false; }
  return true;
}
async function selectRoom(id) {
  if (id === activeRoomId.value) {
    if (switchingRoom.value) { requestVersion++; switchingRoom.value = false; loading.value = false; }
    return;
  }
  if (!await finishRoomEditing()) return;
  const version = ++requestVersion, collectionId = activeCollectionId.value;
  switchingRoom.value = true; error.value = '';
  try {
    // Keep both the list and the old canvas mounted until the next canvas is ready.
    const response = await listPins(collectionId, false, id);
    if (version !== requestVersion || disposed || collectionId !== activeCollectionId.value) return;
    stopDrag();
    activeRoomId.value = id;
    pins.value = response.items || [];
    activeId.value = null; undoIds.value = []; draftPosition.value = null;
    zoom.value = 1;
    writeDraft(`pm-thought-room:${collectionId}`, id);
    await nextTick();
    boardElement.value?.scrollTo(0, 0);
  } catch (exc) { if (version === requestVersion && !disposed) fail(exc); }
  finally {
    if (version === requestVersion && !disposed) { switchingRoom.value = false; loading.value = false; }
  }
}
async function removeRoom() {
  if (!deleteRoomTarget.value || !await finishRoomEditing()) return;
  const id = deleteRoomTarget.value.id;
  saving.value = true; error.value = '';
  try {
    await deleteThoughtRoom(id);
    deleteRoomTarget.value = null;
    if (activeRoomId.value === id) { draft.value = ''; draftPosition.value = null; activeRoomId.value = null; pins.value = []; undoIds.value = []; activeId.value = null; }
    await load();
    store.refreshThoughtCount(activeCollectionId.value).catch(() => {});
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
async function createRoomAutomatically() {
  if (creatingRoom.value || loading.value || !activeCollectionId.value) return;
  creatingRoom.value = true; error.value = '';
  try {
    if (!await finishRoomEditing()) return;
    const collectionId = activeCollectionId.value;
    const room = await createThoughtRoom({ collection_id:collectionId });
    if (disposed || collectionId !== activeCollectionId.value) return;
    // Insert and select the returned item together; avoid reloading the entire list.
    requestVersion++; switchingRoom.value = false;
    rooms.value = [room, ...rooms.value];
    store.setThoughtRoomCount(collectionId, rooms.value.length);
    activeRoomId.value = room.id;
    pins.value = []; activeId.value = null; undoIds.value = []; draft.value = ''; draftPosition.value = null;
    query.value = ''; zoom.value = 1;
    newlyCreatedRoomId.value = room.id;
    clearTimeout(newRoomAnimationTimer);
    newRoomAnimationTimer = setTimeout(() => finishNewRoomAnimation(room.id), 700);
    writeDraft(`pm-thought-room:${collectionId}`, room.id);
    await nextTick();
    document.querySelector(`[data-room-id="${room.id}"]`)?.scrollIntoView({ block:'nearest' });
    boardElement.value?.scrollTo(0, 0);
  } catch (exc) { fail(exc); } finally { creatingRoom.value = false; }
}
async function saveRoom() {
  if (!roomName.value.trim() || !await finishRoomEditing()) return;
  saving.value = true; error.value = '';
  try {
    const room = renameRoomId.value ? await renameThoughtRoom(renameRoomId.value, { title:roomName.value.trim() }) : await createThoughtRoom({ collection_id:activeCollectionId.value, title:roomName.value.trim() });
    roomDialog.value = false;
    if (!renameRoomId.value) { activeRoomId.value = room.id; pins.value = []; activeId.value = null; undoIds.value = []; draftPosition.value = null; writeDraft(`pm-thought-room:${activeCollectionId.value}`, room.id); }
    await load();
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
const store = useNotesStore();
const auth = useAuthStore();
const { activeCollectionId } = storeToRefs(store);
const sortField = ref('created_at'), sortDirection = ref('desc');
const sortOptions = [{ value:'created_at', label:'Erstellungsdatum' }, { value:'updated_at', label:'Letzte Änderung' }, { value:'title', label:'Titel' }];
const sortActions = computed(() => [{ key:'sort', icon:'mdi-tune-variant', label:sortOptions.find((option) => option.value === sortField.value).label, minWidth:240, sections:[
  { key:'field', label:'Sortieren nach', value:sortField.value, options:sortOptions },
  { key:'direction', label:'Reihenfolge', value:sortDirection.value, options:sortField.value === 'color' ? [{ value:'asc', label:'Palettenreihenfolge' },{ value:'desc', label:'Umgekehrte Palettenreihenfolge' }] : sortField.value === 'title' ? [{ value:'asc', label:'A → Z' },{ value:'desc', label:'Z → A' }] : [{ value:'desc', label:'Neueste zuerst' },{ value:'asc', label:'Älteste zuerst' }] }
] }]);
function changeSort({ action, value }) {
  if (action === 'field' && sortOptions.some((option) => option.value === value)) { sortField.value = value; sortDirection.value = ['title','color'].includes(value) ? 'asc' : 'desc'; }
  if (action === 'direction' && ['asc','desc'].includes(value)) sortDirection.value = value;
}
const searchFocused = ref(false), searchScope = ref('all');
const searchScopes = [{ value:'all', label:'Alles' }, { value:'title', label:'Titel' }, { value:'content', label:'Inhalt' }];
const searchScopeLabel = computed(() => searchScopes.find((option) => option.value === searchScope.value).label);
const pins = ref([]), draft = ref(''), query = ref(''), archived = ref(false);
const loading = ref(true), saving = ref(false), error = ref('');
const selectedPinIds = ref([]), selectionBox = ref(null), selectionBusy = ref(false);
let selectionState = null, lastSelectionEnded = 0;
const activeId = ref(null), editingId = ref(null), editText = ref(''), undoIds = ref([]);
const captureInput = ref(null), canvas = ref(null), draftPosition = ref(null), draftGeneration = ref(0);
let dragState = null, lastDragEnded = 0, editTimer = null, editRequest = null, positionRequest = null;
const vAutoHeight = { mounted: resizeTextArea, updated: resizeTextArea };
const CARD_WIDTH = 270;
const draftBounds = ref(null), newCardBounds = ref({});
const draftStyle = computed(() => ({ ...positionStyle(draftPosition.value), ...(draftPosition.value?.title_color ? { '--thought-title-color': draftPosition.value.title_color, '--thought-title-ink': titleInk(draftPosition.value.title_color) } : {}), ...(draftBounds.value ? { width: `${draftBounds.value.width}px`, maxHeight: `${draftBounds.value.height}px` } : {}) }));
function cardStyle(pin) {
  const bounds = newCardBounds.value[pin.id];
  return { ...positionStyle(pinPosition(pin)), ...(pin.title_color ? { '--thought-title-color': pin.title_color, '--thought-title-ink': titleInk(pin.title_color) } : {}), ...(bounds ? { width: `${bounds.width}px` } : {}) };
}
const toolbarColor = computed(() => draftPosition.value?.title_color || pins.value.find((pin) => pin.id === (selectedPinIds.value[0] || activeId.value))?.title_color || defaultTitleColor.value);
async function chooseToolbarColor(color) {
  defaultTitleColor.value = color;
  if (selectedPinIds.value.length) {
    if (positionRequest) await positionRequest;
    if (saving.value || selectionBusy.value || editingId.value) return;
    const selected = pins.value.filter((pin) => selectedPinIds.value.includes(pin.id));
    selectionBusy.value = true; error.value = '';
    try {
      const response = await colorPins({ room_id:activeRoomId.value, ids:selected.map((pin) => pin.id), title_color:color, base_updated_at:Object.fromEntries(selected.map((pin) => [pin.id,pin.updated_at])) });
      for (const updated of response.items) {
        const pin = pins.value.find((item) => item.id === updated.id);
        if (pin) Object.assign(pin,updated);
      }
    } catch (exc) { fail(exc); } finally { selectionBusy.value = false; }
  } else if (draftPosition.value) draftPosition.value = { ...draftPosition.value, title_color:color };
  else {
    const pin = pins.value.find((item) => item.id === activeId.value);
    if (pin) setTitleColor(pin,color);
  }
}
async function deleteSelectedPins() {
  if (selectionBusy.value || !selectedPinIds.value.length) return;
  await archiveItems([...selectedPinIds.value]);
}
function selectionPoint(event) {
  const rect = canvas.value.getBoundingClientRect();
  return { x:bounded((event.clientX-rect.left)/zoom.value), y:bounded((event.clientY-rect.top)/zoom.value) };
}
function startSelection(event) {
  if (event.button !== 0 || event.isPrimary === false || event.pointerType === 'touch' || saving.value || selectionBusy.value || switchingRoom.value || editingId.value) return;
  event.preventDefault();
  window.getSelection()?.removeAllRanges();
  canvas.value?.classList.add('is-selecting');
  document.addEventListener('selectstart', preventNativeSelection);
  selectionState = { pointerId:event.pointerId, start:selectionPoint(event), initial:[...selectedPinIds.value], additive:event.shiftKey || event.ctrlKey || event.metaKey, moved:false };
  window.addEventListener('pointermove', moveSelection);
  window.addEventListener('pointerup', finishSelection);
  window.addEventListener('pointercancel', cancelSelection);
}
function preventNativeSelection(event) { if (selectionState) event.preventDefault(); }
function moveSelection(event) {
  if (!selectionState || event.pointerId !== selectionState.pointerId) return;
  const point = selectionPoint(event), rect = selectionRect(selectionState.start,point);
  if (!selectionState.moved && Math.hypot(rect.width,rect.height)*zoom.value < 5) return;
  event.preventDefault(); window.getSelection()?.removeAllRanges(); selectionState.moved = true; selectionBox.value = rect;
  const cards = pins.value.map((pin) => { const el = document.getElementById(`thought-${pin.id}`); return { id:pin.id,...pinPosition(pin),width:el?.offsetWidth || CARD_WIDTH,height:el?.offsetHeight || 100 }; });
  const ids = intersectingThoughtIds(rect,cards);
  selectedPinIds.value = [...new Set([...(selectionState.additive ? selectionState.initial : []),...ids])];
  activeId.value = selectedPinIds.value.length === 1 ? selectedPinIds.value[0] : null;
}
function stopSelection() {
  document.removeEventListener('selectstart',preventNativeSelection);
  canvas.value?.classList.remove('is-selecting');
  window.removeEventListener('pointermove',moveSelection); window.removeEventListener('pointerup',finishSelection); window.removeEventListener('pointercancel',cancelSelection);
  selectionState = null; selectionBox.value = null;
}
function finishSelection(event) {
  if (!selectionState || event.pointerId !== selectionState.pointerId) return;
  moveSelection(event);
  if (selectionState.moved) lastSelectionEnded = Date.now();
  stopSelection();
}
function cancelSelection() {
  if (selectionState) { selectedPinIds.value = selectionState.initial; activeId.value = selectedPinIds.value.length === 1 ? selectedPinIds.value[0] : null; }
  stopSelection();
}
function modifiedCardSelection(event,pin) {
  if (Date.now() - lastDragEnded < 250) return;
  if (!event.shiftKey && !event.ctrlKey && !event.metaKey) return;
  if (event.target.closest('button')) return;
  event.preventDefault(); event.stopPropagation();
  selectedPinIds.value = selectedPinIds.value.includes(pin.id) ? selectedPinIds.value.filter((id) => id !== pin.id) : [...selectedPinIds.value,pin.id];
  activeId.value = selectedPinIds.value.length === 1 ? selectedPinIds.value[0] : null;
}
watch(activeRoomId, () => { stopSelection(); selectedPinIds.value = []; });
watch(() => pins.value.map((pin) => pin.id), (ids) => { selectedPinIds.value = selectedPinIds.value.filter((id) => ids.includes(id)); });
async function fitThoughts() {
  if (!visiblePins.value.length) return;
  const board = boardElement.value;
  const cards = visiblePins.value.map((pin) => {
    const element = document.getElementById(`thought-${pin.id}`);
    return { ...pinPosition(pin), width:element?.offsetWidth || CARD_WIDTH, height:element?.offsetHeight || 100 };
  });
  const left = Math.min(...cards.map((card) => card.x)), top = Math.min(...cards.map((card) => card.y));
  const right = Math.max(...cards.map((card) => card.x + card.width)), bottom = Math.max(...cards.map((card) => card.y + card.height));
  setCanvasZoom(Math.min((board.clientWidth - 80) / (right - left), (board.clientHeight - 150) / (bottom - top), 2));
  await nextTick();
  board.scrollLeft = Math.max(0, left * zoom.value - 28);
  board.scrollTop = Math.max(0, top * zoom.value - 28);
}
async function arrangeThoughts() {
  if (positionRequest) await positionRequest;
  if (saving.value || editingId.value !== null) return;
  const items = [...visiblePins.value];
  const columns = Math.max(1, Math.floor((boardElement.value.clientWidth / zoom.value - 48) / (CARD_WIDTH + 24)));
  let y = 24, rowHeight = 0;
  saving.value = true; error.value = '';
  try {
    for (let index = 0; index < items.length; index++) {
      if (index && index % columns === 0) { y += rowHeight + 24; rowHeight = 0; }
      const pin = items[index];
      rowHeight = Math.max(rowHeight, document.getElementById(`thought-${pin.id}`)?.offsetHeight || 100);
      const updated = await movePin(pin.id, { position_x:24 + (index % columns) * (CARD_WIDTH + 24), position_y:bounded(y), base_updated_at:pin.updated_at });
      pins.value = pins.value.map((item) => item.id === pin.id ? updated : item);
    }
    await fitThoughts();
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
function titleInk(color) {
  const rgb = color.slice(1).match(/../g).map((part) => parseInt(part, 16) / 255).map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 > .179 ? '#172c32' : '#ffffff';
}
async function setTitleColor(pin, color) {
  if (positionRequest) await positionRequest;
  pin = pins.value.find((item) => item.id === pin.id) || pin;
  if (saving.value || editingId.value !== null) return;
  saving.value = true; error.value = '';
  try {
    const updated = await updatePin(pin.id, { text: pin.text, title_color: color, base_updated_at: pin.updated_at });
    pins.value = pins.value.map((item) => item.id === pin.id ? updated : item);
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
function visiblePlacement(position) {
  const surface = canvas.value.getBoundingClientRect();
  const board = canvas.value.parentElement;
  const view = board.getBoundingClientRect();
  const margin = 8;
  const left = Math.max(surface.left, view.left, 0) + margin;
  const top = Math.max(surface.top, view.top, 0) + margin;
  const right = Math.min(view.left + board.clientWidth, window.innerWidth) - margin;
  const bottom = Math.min(view.top + board.clientHeight, window.innerHeight) - margin;
  if (right <= left || bottom <= top) return null;
  const width = Math.min(CARD_WIDTH, (right - left) / zoom.value);
  const height = Math.min(220, (bottom - top) / zoom.value);
  const screenX = Math.max(left, Math.min(surface.left + position.x * zoom.value, right - width * zoom.value));
  const screenY = Math.max(top, Math.min(surface.top + position.y * zoom.value, bottom - height * zoom.value));
  return { x: bounded((screenX - surface.left) / zoom.value), y: bounded((screenY - surface.top) / zoom.value), width, height };
}
function clearCanvasSelection() {
  if (Date.now() - lastSelectionEnded < 250) return;
  selectedPinIds.value = [];
  activeId.value = null;
  window.getSelection()?.removeAllRanges();
  if (document.activeElement?.closest('.thoughts-card')) document.activeElement.blur();
}
function bounded(value) { return Math.max(0, Math.min(100000, Math.round(value))); }
function positionStyle(position) { return { left: `${position.x}px`, top: `${position.y}px` }; }
function pinPosition(pin) {
  if (pin.position_x != null && pin.position_y != null) return { x: pin.position_x, y: pin.position_y };
  const index = Math.max(0, pins.value.findIndex((item) => item.id === pin.id));
  return { x: 24 + (index % 3) * 310, y: 24 + Math.floor(index / 3) * 360 };
}
const canvasStyle = computed(() => {
  const positions = pins.value.map(pinPosition);
  if (draftPosition.value) positions.push(draftPosition.value);
  return { zoom: zoom.value, width: `${Math.max(1200, ...positions.map((p) => p.x + CARD_WIDTH + 100))}px`, height: `${Math.max(1100, ...positions.map((p) => p.y + 740))}px` };
});
let requestVersion = 0, disposed = false;
const storageKey = computed(() => `pm-thought-draft-v1:${auth.user?.id || auth.username}:${activeCollectionId.value}:${activeRoomId.value || 'pending'}`);
function readDraft(key) { try { return localStorage.getItem(key) || ''; } catch { return ''; } }
function writeDraft(key, value) { try { value ? localStorage.setItem(key, value) : localStorage.removeItem(key); } catch { /* Storage optional. */ } }
watch(draft, (text) => writeDraft(storageKey.value, text), { flush: 'sync' });
watch(draftPosition, (position) => writeDraft(`${storageKey.value}:position`, position ? JSON.stringify(position) : ''), { flush: 'sync' });
watch(editText, (text) => {
  if (!editingId.value) return;
  writeDraft(`${storageKey.value}:edit:${editingId.value}`, text);
  clearTimeout(editTimer);
  const pin = pins.value.find((item) => item.id === editingId.value);
  if (pin && text.trim() && text !== pin.text) editTimer = setTimeout(() => saveEdit(pin, false), 600);
}, { flush: 'sync' });
const visiblePins = computed(() => pins.value);
const showThoughtsEmptyState = computed(() => (
  !loading.value
  && !error.value
  && !archived.value
  && !draftPosition.value
  && !visiblePins.value.length
));
const visibleRooms = computed(() => {
  const search = (query.value || '').trim().toLocaleLowerCase('de');
  return sortThoughts(rooms.value.filter((room) => {
    const text = searchScope.value === 'title' ? room.title : searchScope.value === 'content' ? room.content : `${room.title} ${room.content}`;
    return !search || text.toLocaleLowerCase('de').includes(search);
  }).map((room) => ({ ...room, text:room.title })), sortField.value, sortDirection.value);
});
watch(() => pins.value.map((pin) => [pin.id, pin.text, pin.updated_at]), () => {
  const items = pins.value;
  const room = rooms.value.find((item) => item.id === activeRoomId.value);
  if (room) { room.content = items.map((pin) => pin.text).join('\n'); if (items.length) room.updated_at = items.reduce((date,pin) => pin.updated_at > date ? pin.updated_at : date,room.updated_at); }
});
function listDateLabel(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const time = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });

  if (date.toDateString() === now.toDateString()) return `heute ${time}`;
  if (date.toDateString() === yesterday.toDateString()) return `gestern ${time}`;

  // Gleiches Format wie die Dokumentliste (TT.MM.JJJJ).
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
const dateLabel = (value) => new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
function fail(exc) { error.value = mapApiError(exc) || exc.message || 'Die Gedanken konnten nicht gespeichert werden.'; }
async function load() {
  const version = ++requestVersion, collectionId = activeCollectionId.value, archive = archived.value;
  if (!collectionId) { loading.value = false; return; }
  loading.value = true; error.value = '';
  try {
    const roomItems = await listThoughtRooms(collectionId);
    if (version !== requestVersion || disposed) return;
    rooms.value = roomItems;
    store.setThoughtRoomCount(collectionId, roomItems.length);
    if (!roomItems.some((room) => room.id === activeRoomId.value)) activeRoomId.value = roomItems.find((room) => room.id === readDraft(`pm-thought-room:${collectionId}`))?.id || roomItems[0]?.id;
    const response = await listPins(collectionId, archive, activeRoomId.value);
    if (version === requestVersion && !disposed) {
      pins.value = response.items || [];
      // A reload during a completed save must not resurrect a duplicate draft.
      if (draftPosition.value?.id && pins.value.some((pin) => pin.id === draftPosition.value.id && pin.text === draft.value)) {
        draft.value = ''; draftPosition.value = null;
      }
    }
  } catch (exc) { if (version === requestVersion && !disposed) fail(exc); }
  finally { if (version === requestVersion && !disposed) loading.value = false; }
}
watch(activeCollectionId, () => {
  stopDrag();
  activeRoomId.value = null; rooms.value = [];
  draft.value = readDraft(storageKey.value);
  let position = null;
  try { position = JSON.parse(readDraft(`${storageKey.value}:position`)); } catch { /* Older drafts have no position. */ }
  draftPosition.value = draft.value ? { title_color: position?.title_color || null, created_at: position?.created_at || new Date().toISOString(), id: position?.id || crypto.randomUUID(), x: bounded(position?.x ?? 24), y: bounded(position?.y ?? 24) } : null;
  pins.value = []; editingId.value = null; activeId.value = null; undoIds.value = [];
  switchingRoom.value = false;
  load();
}, { immediate: true });
watch(activeRoomId, (id) => {
  if (!id) return;
  const legacyKey = `pm-thought-draft-v1:${auth.user?.id || auth.username}:${activeCollectionId.value}`;
  const key = storageKey.value;
  const legacy = !readDraft(key) && rooms.value[0]?.id === id ? readDraft(legacyKey) : '';
  draft.value = readDraft(key) || legacy;
  let position = null;
  try { position = JSON.parse(readDraft(`${legacy ? legacyKey : key}:position`)); } catch { /* No saved position. */ }
  draftPosition.value = draft.value ? { title_color:position?.title_color || null, created_at:position?.created_at || new Date().toISOString(), id:position?.id || crypto.randomUUID(), x:bounded(position?.x ?? 24), y:bounded(position?.y ?? 24) } : null;
  if (legacy) { writeDraft(legacyKey, ''); writeDraft(`${legacyKey}:position`, ''); }
});
watch(archived, () => { pins.value = []; activeId.value = null; load(); });
// Schnellerfassung aus der Command-Palette: offene Fläche nachladen, ohne laufende Eingaben zu stören.
watch(() => store.thoughtRevision, () => { if (!saving.value && editingId.value === null && !archived.value) load(); });
store.ensureCollectionsLoaded().catch(fail);
function captureOnBlur(event) { if (!event.relatedTarget?.closest('.thoughts-capture, .thought-color-menu, .thoughts-toolbar')) capture(); }
function captureShortcut(event) { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && !event.isComposing) { event.preventDefault(); capture(); } }
async function capture() {
  if (saving.value || loading.value || editingId.value !== null || !draft.value.trim() || !activeCollectionId.value) return;
  const collectionId = activeCollectionId.value, text = draft.value, key = storageKey.value;
  saving.value = true; error.value = '';
  try {
    const pin = await createPin({ request_id: draftPosition.value?.id, title_color: draftPosition.value?.title_color || null, room_id:activeRoomId.value, collection_id: collectionId, text, position_x: draftPosition.value?.x ?? 24, position_y: draftPosition.value?.y ?? 24 });
    writeDraft(key, '');
    if (collectionId === activeCollectionId.value && !disposed) {
      newCardBounds.value = { ...newCardBounds.value, [pin.id]: draftBounds.value };
      draft.value = ''; draftPosition.value = null; draftBounds.value = null; activeId.value = null; query.value = ''; if (!archived.value && pin.status === 'open') { const alreadyListed = pins.value.some((item) => item.id === pin.id); pins.value = [pin, ...pins.value.filter((item) => item.id !== pin.id)]; const room = rooms.value.find((item) => item.id === pin.room_id); if (room && !alreadyListed) room.note_count = (room.note_count || 0) + 1; }
      await nextTick();
    }
    store.refreshThoughtCount(collectionId).catch(() => {});
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
async function focusPin(id) { activeId.value = id; await nextTick(); const card = document.getElementById(`thought-${id}`); card?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); card?.focus({ preventScroll: true }); }
async function createAtClick(event) {
  if (Date.now() - Math.max(lastDragEnded,lastSelectionEnded) < 250) return;
  const rect = canvas.value.getBoundingClientRect();
  await startDraft({ x: bounded((event.clientX - rect.left) / zoom.value), y: bounded((event.clientY - rect.top) / zoom.value) });
}
async function createFromButton() {
  if (selectionBusy.value || switchingRoom.value || saving.value || loading.value || !activeCollectionId.value || !activeRoomId.value) return;
  if (editingId.value) {
    await saveEdit(pins.value.find((pin) => pin.id === editingId.value));
    if (editingId.value) return;
  }
  if (draft.value.trim()) { await capture(); if (draft.value.trim()) return; }
  const board = boardElement.value;
  if (!canvas.value || !board) return;
  const occupied = pins.value.map((pin) => {
    const element = document.getElementById(`thought-${pin.id}`);
    return { ...pinPosition(pin), width:element?.offsetWidth || CARD_WIDTH, height:element?.offsetHeight || 100 };
  });
  function searchVisible() {
    const surface = canvas.value.getBoundingClientRect(), view = board.getBoundingClientRect();
    const x = Math.max(8, (Math.max(surface.left, view.left, 0) + 16 - surface.left) / zoom.value);
    const y = Math.max(8, (Math.max(surface.top, view.top + 80, 0) + 16 - surface.top) / zoom.value);
    const width = (Math.min(view.left + board.clientWidth, window.innerWidth) - 16 - surface.left) / zoom.value - x;
    const height = (Math.min(view.top + board.clientHeight, window.innerHeight) - 76 - surface.top) / zoom.value - y;
    return findFreeThoughtPosition({ x,y,width,height }, { width:Math.min(CARD_WIDTH,width),height:Math.min(220,height) }, occupied);
  }
  let position = searchVisible();
  if (!position) {
    const y = Math.max(24, ...occupied.map((card) => card.y + card.height + THOUGHT_PLACEMENT_GAP));
    const surface = canvas.value.getBoundingClientRect(), view = board.getBoundingClientRect();
    // Extend first so scrolling can reveal an unoccupied area even past the current canvas.
    canvas.value.style.height = `${Math.max(canvas.value.offsetHeight, y + board.clientHeight / zoom.value)}px`;
    board.scrollLeft = 0;
    board.scrollTop += surface.top + y * zoom.value - view.top - 100;
    await nextTick();
    position = searchVisible();
  }
  if (position) await startDraft(position);
}
async function startDraft(position) {
  if (archived.value || saving.value || loading.value || !activeCollectionId.value || !activeRoomId.value) return;
  if (editingId.value) {
    const pin = pins.value.find((item) => item.id === editingId.value);
    if (!editText.value.trim()) return;
    await saveEdit(pin);
    if (editingId.value) return;
  }
  if (draft.value.trim()) {
    await capture();
    if (draft.value.trim()) return;
  }
  const placement = visiblePlacement(position);
  if (!placement) return;
  draftBounds.value = { width: placement.width, height: placement.height };
  draftPosition.value = { x: placement.x, y: placement.y, id: crypto.randomUUID(), title_color:defaultTitleColor.value, created_at: new Date().toISOString() }; draftGeneration.value++;
  await nextTick(); resizeTextArea(captureInput.value); captureInput.value?.focus({ preventScroll: true });
}
function dismissEmptyDraftOutside(event) {
  if (!draftPosition.value || saving.value) return;
  const card = captureInput.value?.closest('.thoughts-capture');
  if (card && !event.composedPath().includes(card) && !event.target.closest('.thought-color-menu, .thoughts-toolbar')) {
    if (draft.value.trim()) { capture(); return; }
    draft.value = '';
    draftPosition.value = null;
    draftBounds.value = null;
  }
}
function closeDraft() {
  if (draft.value.trim()) { capture(); return; }
  draft.value = ''; draftPosition.value = null;
}
function startDrag(event, pin) {
  if (event.target.closest('button, input, textarea, select, a')) return;
  if (event.button !== 0 || selectionBusy.value || switchingRoom.value || positionRequest || saving.value || editingId.value || event.isPrimary === false) return;
  event.preventDefault();
  const items = moveSelectionSnapshots(pin);
  dragState = { items, clientX:event.clientX, clientY:event.clientY, pointerId:event.pointerId };
  activeId.value = pin.id;
  window.addEventListener('pointermove', dragMove);
  window.addEventListener('pointerup', finishDrag);
  window.addEventListener('pointercancel', cancelDrag);
}
function moveSelectionSnapshots(pin) {
  if (!selectedPinIds.value.includes(pin.id)) selectedPinIds.value = [pin.id];
  return pins.value.filter((item) => selectedPinIds.value.includes(item.id)).map((item) => ({ pin:{ ...item },position:pinPosition(item) }));
}
function applyGroupPositions(positions) {
  for (const position of positions) {
    const current = pins.value.find((pin) => pin.id === position.id);
    if (current) { current.position_x = position.x; current.position_y = position.y; }
  }
}
function dragMove(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) return;
  const { items,clientX,clientY } = dragState;
  applyGroupPositions(shiftedThoughtPositions(items,(event.clientX-clientX)/zoom.value,(event.clientY-clientY)/zoom.value));
}
function stopDrag() {
  window.removeEventListener('pointermove', dragMove);
  window.removeEventListener('pointerup', finishDrag);
  window.removeEventListener('pointercancel', cancelDrag);
  dragState = null;
}
function cancelDrag() {
  if (dragState) for (const { pin } of dragState.items) {
    const current = pins.value.find((item) => item.id === pin.id);
    if (current) Object.assign(current,pin);
  }
  stopDrag();
}
function finishDrag(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) return;
  dragMove(event); lastDragEnded = Date.now();
  const items = dragState.items;
  const changed = items.some(({ pin,position }) => { const current = pins.value.find((item) => item.id === pin.id); return current && (current.position_x !== position.x || current.position_y !== position.y); });
  stopDrag();
  if (changed) persistPositions(items);
}
async function persistPositions(items) {
  if (positionRequest) return;
  const collectionId = activeCollectionId.value, roomId = activeRoomId.value;
  const updates = items.map(({ pin }) => { const current = pins.value.find((item) => item.id === pin.id); return { id:pin.id, position_x:current.position_x, position_y:current.position_y, base_updated_at:pin.updated_at }; });
  error.value = '';
  positionRequest = (async () => {
    try {
      const response = await movePins({ room_id:roomId,items:updates });
      if (!disposed && collectionId === activeCollectionId.value && roomId === activeRoomId.value) for (const updated of response.items) {
        const current = pins.value.find((item) => item.id === updated.id);
        if (current) Object.assign(current,updated);
      }
    } catch (exc) {
      if (!disposed && collectionId === activeCollectionId.value && roomId === activeRoomId.value) {
        for (const { pin } of items) { const current = pins.value.find((item) => item.id === pin.id); if (current) Object.assign(current,pin); }
        fail(exc);
      }
    }
  })();
  await positionRequest; positionRequest = null;
}
function moveWithKeys(event,pin) {
  if (event.target !== event.currentTarget) return;
  const directions = { ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1] };
  if (!directions[event.key] || positionRequest || selectionBusy.value || switchingRoom.value || saving.value || editingId.value) return;
  event.preventDefault();
  const [dx,dy] = directions[event.key],step = event.shiftKey ? 5 : 20;
  const items = moveSelectionSnapshots(pin);
  applyGroupPositions(shiftedThoughtPositions(items,dx*step,dy*step));
  persistPositions(items);
}
async function editPin(pin, event = null) {
  if (positionRequest) await positionRequest;
  pin = pins.value.find((item) => item.id === pin.id) || pin;
  if (selectionBusy.value || switchingRoom.value || editingId.value || saving.value) return;
  // Place the writing cursor at the clicked text position when the browser exposes it.
  let cursorOffset = event?.currentTarget?.selectionStart ?? null;
  if (cursorOffset === null && event?.currentTarget && event.detail) {
    const caret = document.caretPositionFromPoint?.(event.clientX, event.clientY);
    const range = caret ? null : document.caretRangeFromPoint?.(event.clientX, event.clientY);
    const node = caret?.offsetNode || range?.startContainer;
    const offset = caret?.offset ?? range?.startOffset;
    if (node && event.currentTarget.contains(node)) {
      const prefix = document.createRange();
      prefix.selectNodeContents(event.currentTarget);
      prefix.setEnd(node, offset);
      cursorOffset = prefix.toString().length;
    }
  }
  selectedPinIds.value = [pin.id];
  editingId.value = pin.id; editText.value = readDraft(`${storageKey.value}:edit:${pin.id}`) || pin.text;
  activeId.value = pin.id; await nextTick();
  const input = document.getElementById(`thought-${pin.id}`)?.querySelector('textarea');
  resizeTextArea(input);
  input?.focus({ preventScroll: true });
  const offset = cursorOffset ?? input?.value.length ?? 0;
  input?.setSelectionRange(offset, offset);
}
async function saveEdit(pin, finish = true) {
  clearTimeout(editTimer);
  if (editRequest) await editRequest;
  if (!pin || editingId.value !== pin.id || disposed) return;
  const current = pins.value.find((item) => item.id === pin.id);
  const text = editText.value;
  if (!text.trim()) { error.value = 'Ein Gedanke darf nicht leer sein.'; return; }
  if (text === current?.text) { if (finish) editingId.value = null; return; }
  const collectionId = activeCollectionId.value, key = `${storageKey.value}:edit:${pin.id}`;
  saving.value = true; error.value = '';
  editRequest = (async () => {
    try {
      const updated = await updatePin(pin.id, { text, base_updated_at: current.updated_at });
      if (!disposed && collectionId === activeCollectionId.value) {
        pins.value = pins.value.map((item) => item.id === pin.id ? updated : item);
        if (editText.value === text) {
          writeDraft(key, '');
          if (finish) editingId.value = null;
        }
      }
    } catch (exc) { fail(exc); }
    finally { saving.value = false; }
  })();
  await editRequest;
  editRequest = null;
  if (finish && editingId.value === pin.id && editText.value !== text) await saveEdit(pin);
}
async function archiveItems(ids, archive = !archived.value) {
  if (selectionBusy.value) return;
  if (positionRequest) await positionRequest;
  if (saving.value || editingId.value !== null) return;
  const collectionId = activeCollectionId.value;
  saving.value = true; error.value = '';
  try {
    await archivePins(collectionId, ids, archive);
    if (collectionId === activeCollectionId.value && !disposed) {
      undoIds.value = archive ? [...ids] : []; await load();
    }
    store.refreshThoughtCount(collectionId).catch(() => {});
  } catch (exc) { fail(exc); } finally { saving.value = false; }
}
const undoArchive = () => archiveItems([...undoIds.value], false);
onMounted(() => window.addEventListener('pointerdown', dismissEmptyDraftOutside, true));
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', dismissEmptyDraftOutside, true);
  clearTimeout(editTimer);
  stopSelection();
  stopDrag(); disposed = true; requestVersion++;
});
</script>

<style scoped>
.thoughts-ws { display:flex; height:100%; min-width:0; min-height:0; overflow:hidden; color:var(--pm-text, #263c42); background:var(--pm-content-surface,#fff); }
.thoughts-inbox { display:flex; flex-direction:column; flex:0 0 clamp(300px,31vw,380px); min-height:0; background:var(--pm-content-surface,#fff); border-right:1px solid var(--pm-divider,#d8dfe1); }
.thoughts-header { min-height:57px; padding:0 20px; display:flex; align-items:center; gap:12px; border-bottom:1px solid var(--pm-divider,#d8dfe1); }
h1,h2,p { margin:0; } h1 { font-size:18px; font-weight:650; }.thoughts-header>span { font-size:12px; color:var(--pm-muted,#71818a); }
.thoughts-board button,input,textarea,select { font:inherit; } .thoughts-board button,.thoughts-error button { cursor:pointer; border-radius:7px; padding:6px 8px; color:inherit; }.thoughts-board button:hover,.thoughts-error button:hover { background:rgba(110,140,145,.1); }button:disabled { opacity:.45; cursor:default; }
button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible { outline:2px solid var(--pm-accent,#26736b); outline-offset:2px; }
.thoughts-context { display:flex; align-items:center; padding:10px 14px; gap:8px; font-size:12px; border-bottom:1px solid var(--pm-divider,#d8dfe1); }.thoughts-context select { flex:1; min-width:0; color:inherit; }.thoughts-context button { margin-left:auto; }
textarea { display:block; width:100%; resize:none; min-height:22.1px; max-height:none; overflow:hidden; border:0; border-radius:0; padding:0; line-height:1.7; font-size:13px; color:inherit; background:transparent; }
.thoughts-capture { cursor:text; }.thoughts-capture textarea { flex:none; min-height:22.1px; max-height:none; resize:none; }.thoughts-capture>header,.thoughts-capture>footer { flex-shrink:0; }.thoughts-capture footer { align-items:center; justify-content:space-between; }.thoughts-capture small { font-size:10px; color:var(--pm-muted,#71818a); }button.thoughts-primary { background:var(--pm-accent,#26736b); color:#fff; padding:7px 12px; font-size:12px; }
.thoughts-card textarea::placeholder { color:var(--pm-muted,#71818a); opacity:1; }
.thoughts-card textarea, .thoughts-card textarea:focus, .thoughts-card textarea:focus-visible { outline:none; border:0; box-shadow:none; background:transparent; }
.thoughts-text--editable { cursor:text; border-radius:3px; }.thoughts-text--editable:focus-visible { outline:2px solid var(--pm-accent,#26736b); outline-offset:5px; }

.thoughts-search { display:flex; align-items:center; gap:8px; padding:12px 16px; }.thoughts-search input { width:100%; min-width:0; font-size:12px; color:inherit; }.thoughts-selection { display:flex; align-items:center; gap:4px; padding:6px 12px; font-size:11px; background:rgba(72,131,124,.1); }.thoughts-selection span { margin-right:auto; }
.thoughts-list { overflow:auto; flex:1; padding:0 8px 20px; }.thoughts-day { font-size:10px; font-weight:650; color:var(--pm-muted,#71818a); padding:15px 10px 7px; }.thoughts-list-row { display:flex; gap:8px; padding:10px; border-radius:9px; margin-bottom:3px; }.thoughts-list-row input { align-self:flex-start; margin-top:4px; accent-color:var(--pm-accent,#26736b); }.thoughts-list-open { text-align:left; flex:1; min-width:0; padding:0; }.thoughts-list-open>span { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; white-space:pre-wrap; font-size:12px; line-height:1.55; overflow-wrap:anywhere; }.thoughts-list-open small { display:block; font-size:10px; margin-top:5px; opacity:.6; }.is-selected,.thoughts-list-row.is-active { background:rgba(72,131,124,.1); }
.thoughts-board { position:relative; min-width:0; flex:1; overflow:auto; padding:28px; }
.thoughts-canvas { position:relative; min-width:100%; cursor:default; background:transparent; border-radius:12px; }

.thoughts-titlebar { cursor:grab; touch-action:none; user-select:none; min-height:26px; border-radius:4px; }.thoughts-titlebar:active { cursor:grabbing; }.thoughts-titlebar.is-disabled { cursor:default; }.thoughts-titlebar:focus-visible { outline:2px solid var(--pm-accent,#26736b); outline-offset:3px; }
.thoughts-card--growing { animation:thought-bloom 360ms cubic-bezier(.16,1,.3,1) both; transform-origin:top left; z-index:3; }
.thought-dismiss-leave-active { animation:none; transition:opacity 180ms ease, transform 180ms ease; pointer-events:none; transform-origin:center; }
.thought-dismiss-leave-to { opacity:0; transform:translateY(6px) scale(.94); }
@media(prefers-reduced-motion:reduce) { .thought-dismiss-leave-active { transition:none; } }
@keyframes thought-bloom { from { opacity:0; transform:translateY(8px) scale(.15) rotate(-5deg); } to { opacity:1; transform:translateY(0) scale(1) rotate(0); } }
@media(prefers-reduced-motion:reduce) { .thoughts-card--growing { animation:none; } }
.thoughts-card { position:absolute; width:270px; overflow:auto; cursor:default; padding:16px; border:1px solid var(--pm-divider,#d8dfe1); border-radius:12px; color:var(--pm-text,#263c42); background:var(--pm-app-surface-raised,#fff); box-shadow:var(--pm-document-row-shadow,0 2px 8px rgba(30,55,60,.08)); }.thoughts-card.is-active { z-index:2; }.thoughts-card.is-active,.thoughts-card.is-selected { border-color:var(--pm-accent,#26736b); }.thoughts-card>header { display:flex; align-items:center; justify-content:space-between; box-sizing:border-box; height:32px; min-height:32px; font-size:10px; line-height:1; margin:-16px -16px 12px; padding:3px 10px; border-bottom:1px solid color-mix(in srgb, var(--pm-accent,#26736b) 28%, var(--pm-divider,#d8dfe1)); border-radius:11px 11px 0 0; color:var(--thought-title-ink,var(--pm-text,#263c42)); background:var(--thought-title-color,color-mix(in srgb, var(--pm-accent,#26736b) 24%, var(--pm-content-surface,#fff))); }.thoughts-card-meta { flex:1; display:flex; gap:8px; align-items:center; }.thoughts-card input { accent-color:var(--pm-accent,#26736b); }.thoughts-card time { flex:1; font-size:10px; color:inherit; }.thoughts-card header button { display:flex; align-items:center; justify-content:center; box-sizing:border-box; width:23px; height:23px; flex:0 0 23px; padding:3px; line-height:1; }.thoughts-text { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; font-size:13px; }.thoughts-tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:12px; }.thoughts-tags button { font-size:10px; color:var(--pm-accent,#26736b); background:rgba(72,131,124,.08); padding:3px 6px; }.thoughts-card footer { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }.thoughts-card footer button { display:flex; align-items:center; gap:5px; font-size:10px; }.thoughts-edit { min-height:22.1px; outline:none; }.thoughts-edit:focus-visible { outline:none; }
/* Keep the card still while its controls quietly appear on interaction. */
.thoughts-card button,
.thoughts-card input[type="checkbox"],
.thoughts-card footer small {
  opacity:0;
  pointer-events:none;
  transition:opacity 140ms ease;
}
.thoughts-card:hover button,
.thoughts-card:hover input[type="checkbox"],
.thoughts-card:hover footer small,
.thoughts-card:has(:focus-visible) button,
.thoughts-card:has(:focus-visible) input[type="checkbox"],
.thoughts-card:has(:focus-visible) footer small {
  opacity:1;
  pointer-events:auto;
}
@media (hover:none) {
  .thoughts-card:focus-within button,
  .thoughts-card:focus-within input[type="checkbox"],
  .thoughts-card:focus-within footer small { opacity:1; pointer-events:auto; }
}
@media (prefers-reduced-motion:reduce) {
  .thoughts-card button, .thoughts-card input[type="checkbox"], .thoughts-card footer small { transition:none; }
}

.thoughts-muted { padding:24px 12px; font-size:12px; color:var(--pm-muted,#71818a); }.thoughts-error { margin:8px 16px; padding:10px; font-size:12px; color:var(--pm-danger,#a33); background:rgba(180,40,40,.05); }.thoughts-feedback { display:flex; align-items:center; gap:10px; margin-bottom:15px; font-size:12px; }.thoughts-feedback button { text-decoration:underline; }.thoughts-board-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; min-height:280px; color:var(--pm-muted,#71818a); font-size:13px; }
.thoughts-board-empty--visual { position:absolute; inset:0; z-index:2; min-height:0; padding:28px; color:var(--pm-text,#263c42); text-align:center; pointer-events:none; }
.thoughts-empty-visual { position:relative; width:188px; height:134px; margin-bottom:4px; animation:thoughts-empty-enter 480ms cubic-bezier(.16,1,.3,1) both; }
.thoughts-empty-visual::before { content:''; position:absolute; inset:10px -28px -10px; border-radius:50%; background:radial-gradient(ellipse, color-mix(in srgb, var(--pm-accent,#26736b) 18%, transparent), transparent 68%); }
.thoughts-empty-card { position:absolute; display:flex; flex-direction:column; gap:8px; width:92px; height:112px; padding:15px 13px; border:1px solid color-mix(in srgb, var(--pm-text,#263c42) 18%, var(--pm-divider,#d8dfe1)); border-radius:14px; background:var(--pm-app-surface-raised,#fff); box-shadow:0 14px 28px rgba(20,50,54,.12); animation:thoughts-empty-card-in 620ms cubic-bezier(.22,1,.36,1) both; }
.thoughts-empty-card i { width:25px; height:8px; border-radius:99px; background:var(--pm-accent,#26736b); opacity:.76; }.thoughts-empty-card b { display:block; height:6px; border-radius:99px; background:color-mix(in srgb, var(--pm-text,#263c42) 16%, transparent); }.thoughts-empty-card b:last-child { width:72%; }
.thoughts-empty-card--one { left:10px; bottom:5px; transform:rotate(-10deg); background:color-mix(in srgb, #75d6dd 16%, var(--pm-app-surface-raised,#fff)); animation-delay:90ms; }.thoughts-empty-card--two { right:9px; bottom:3px; transform:rotate(9deg); background:color-mix(in srgb, #f5ba70 18%, var(--pm-app-surface-raised,#fff)); animation-delay:160ms; }.thoughts-empty-card--two i { background:#d78a32; }
.thoughts-empty-plus { position:absolute; z-index:2; right:5px; bottom:0; display:grid; place-items:center; width:42px; height:42px; border:3px solid var(--pm-content-surface,#fff); border-radius:50%; color:var(--pm-on-accent,#fff); background:var(--pm-accent,#26736b); box-shadow:0 8px 18px color-mix(in srgb, var(--pm-accent,#26736b) 30%, transparent); animation:thoughts-empty-plus-in 520ms cubic-bezier(.34,1.56,.64,1) 300ms both; }
.thoughts-empty-spark { position:absolute; z-index:3; color:var(--pm-accent,#26736b); font-size:21px; line-height:1; animation:thoughts-empty-spark 2.8s ease-in-out .7s infinite; }.thoughts-empty-spark--one { top:7px; left:20px; }.thoughts-empty-spark--two { top:23px; right:5px; font-size:13px; animation-delay:1.15s; }
.thoughts-empty-copy { display:flex; flex-direction:column; align-items:center; gap:8px; max-width:360px; }.thoughts-empty-copy h2 { margin:0; font-size:20px; font-weight:650; letter-spacing:-.02em; }.thoughts-empty-copy p { margin:0; color:var(--pm-muted,#71818a); font-size:13px; line-height:1.55; }.thoughts-empty-action { display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:38px; margin-top:8px; padding:0 15px; border:1px solid color-mix(in srgb, var(--pm-accent,#26736b) 62%, transparent); border-radius:10px; color:var(--pm-accent,#26736b); background:color-mix(in srgb, var(--pm-accent,#26736b) 9%, transparent); font:600 12.5px/1 var(--pm-font-sans,inherit); cursor:pointer; pointer-events:auto; transition:transform 160ms ease,background 160ms ease; }.thoughts-empty-action:hover:not(:disabled) { transform:translateY(-1px); background:color-mix(in srgb, var(--pm-accent,#26736b) 15%, transparent); }.thoughts-empty-action:disabled { opacity:.5; cursor:default; }
@keyframes thoughts-empty-enter { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } } @keyframes thoughts-empty-card-in { from { opacity:0; transform:translateY(18px) scale(.78) rotate(0); } to { opacity:1; } } @keyframes thoughts-empty-plus-in { from { opacity:0; transform:scale(.45) rotate(-28deg); } to { opacity:1; transform:scale(1) rotate(0); } } @keyframes thoughts-empty-spark { 0%,100% { opacity:.28; transform:scale(.7) rotate(0); } 50% { opacity:1; transform:scale(1.15) rotate(12deg); } }
@media(prefers-reduced-motion:reduce) { .thoughts-empty-visual,.thoughts-empty-card,.thoughts-empty-plus,.thoughts-empty-spark { animation:none; } }
.thoughts-list .document-list-body,.thoughts-list .document-list-content { display:flex; flex:1; min-height:100%; }.thoughts-list-empty { display:flex; flex:1; width:100%; min-height:280px; align-items:center; justify-content:center; }
@media(max-width:850px) { .thoughts-board { padding:20px; } }
@media(max-width:650px) { .thoughts-ws { flex-direction:column; overflow:auto; }.thoughts-inbox { flex:0 0 auto; border-right:0; }.thoughts-list { max-height:230px; }.thoughts-board { flex:0 0 auto; overflow:visible; }.thoughts-board-empty { min-height:160px; } }
</style>

<style scoped>
.thoughts-card :deep(.color-trigger) { opacity:0; pointer-events:none; transition:opacity 140ms ease; }
.thoughts-card:hover :deep(.color-trigger), .thoughts-card:focus-within :deep(.color-trigger) { opacity:1; pointer-events:auto; }
@media(prefers-reduced-motion:reduce) { .thoughts-card :deep(.color-trigger) { transition:none; } }
</style>

<style scoped>
.thoughts-inbox { background:var(--pm-content-surface,#fff); }
.thoughts-header { position:relative; flex:none; box-sizing:border-box; height:57px; min-height:57px; align-items:center; justify-content:space-between; gap:12px; padding:10px 14px; background:rgba(var(--v-theme-surface),.68); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); }
.thoughts-heading { flex:0 1 auto; min-width:0; max-width:40%; margin-right:14px; overflow:hidden; transition:max-width 220ms ease,opacity 140ms ease,margin 220ms ease; }
.thoughts-header h1 { line-height:inherit; color:var(--pm-text); font-size:.98rem; font-weight:600; white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }
.thoughts-header--search-focused .thoughts-heading { max-width:0; opacity:0; margin-right:-12px; pointer-events:none; }
.thoughts-header .pm-searchbar { flex:1 1 auto; min-width:120px; }
.thoughts-list.document-list-shell { padding:0; min-height:0; height:auto; }
</style>

<style scoped>
.thoughts-ws { position:relative; --thoughts-list-width:clamp(300px,31vw,380px); }
.thoughts-inbox { position:relative; width:var(--thoughts-list-width); min-width:0; overflow:hidden; flex:0 0 var(--thoughts-list-width); transition:margin-left 260ms cubic-bezier(.16,1,.3,1),opacity 180ms ease,transform 260ms cubic-bezier(.16,1,.3,1),visibility 0ms; }
.thoughts-ws.is-list-collapsed .thoughts-inbox { margin-left:calc(-1 * var(--thoughts-list-width)); opacity:0; pointer-events:none; transform:translateX(-18px); visibility:hidden; transition-delay:0ms,0ms,0ms,260ms; }
.thoughts-list-handle { position:absolute; z-index:6; top:50%; left:var(--thoughts-list-width); display:flex; align-items:center; justify-content:center; width:22px; height:52px; padding:0; transform:translate(-1px,-50%); color:var(--pm-muted,#5b6b70); background:var(--pm-content-surface,#fff); border:1px solid var(--pm-divider,#d8dfe1); border-left:0; border-radius:0 11px 11px 0; box-shadow:2px 0 10px -6px rgba(15,23,25,.28); opacity:.85; transition:left 260ms cubic-bezier(.16,1,.3,1),color 160ms ease,opacity 160ms ease,box-shadow 160ms ease; }
.thoughts-ws.is-list-collapsed .thoughts-list-handle { left:0; }
.thoughts-list-handle:hover { background:var(--pm-content-surface,#fff); color:var(--pm-text,#1f2b2e); opacity:1; box-shadow:3px 0 14px -6px rgba(15,23,25,.34); }
.thoughts-list-handle:focus-visible { outline:2px solid rgb(var(--v-theme-primary)); outline-offset:2px; opacity:1; }
@media(max-width:920px) { .thoughts-ws { --thoughts-list-width:clamp(280px,42%,380px); }.thoughts-heading { max-width:150px; } }
@media(max-width:650px) { .thoughts-inbox { width:100%; flex:0 0 auto; } }
@media(prefers-reduced-motion:reduce) { .thoughts-inbox,.thoughts-list-handle { transition:none; } }
</style>

<style scoped>
.notes-ws__list {
  display: block;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-anchor: none;
}

/* Kompakte Zeile (Listen-Sprache, Variante A): keine Karte, feine
   Trennlinien; Hover = leichte Tönung, Auswahl = Akzentbalken + Tönung.
   Farben/Typo aus den gemeinsamen --pm-list-*-Tokens (theme/lists.css). */
.notes-ws__list {
  --notes-row-height: 112px;
}

.notes-ws__item {
  position: relative;
  box-sizing: border-box;
  height: var(--notes-row-height);
  min-height: var(--notes-row-height);
  overflow: hidden;
  border: 0;
  border-bottom: 1px solid var(--pm-list-divider);
  border-radius: 0;
  background: transparent;
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    box-shadow var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.notes-ws__item:last-child {
  border-bottom-color: transparent;
}

.notes-ws__item:hover {
  background: var(--pm-list-hover);
}

.notes-ws__item.is-active,
.notes-ws__item.is-active:hover {
  background: var(--pm-list-selected);
  box-shadow: inset 3px 0 0 var(--pm-list-accent);
}

.notes-ws__item-select {
  display: flex;
  width: 100%;
  height: 100%;
  flex-direction: column;
  gap: 4px;
  padding: 11px 14px 11px 15px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.notes-ws__item-head { min-width: 0; }

.notes-ws__item-title {
  min-width: 0;
  overflow: hidden;
  color: var(--pm-list-title);
  font-size: 0.94rem;
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.notes-ws__item-title.is-untitled {
  color: var(--pm-list-meta-soft);
  font-style: italic;
  font-weight: 500;
}

.thoughts-room-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  margin-right: 60px;
  color: var(--pm-list-meta-soft);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.notes-ws__item-snippet {
  display: -webkit-box;
  margin-right: 60px;
  overflow: hidden;
  color: var(--pm-list-meta);
  font-size: 0.8rem;
  line-height: 1.42;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.notes-ws__item-delete,
.notes-ws__item-pin {
  position: absolute;
  right: 8px;
  bottom: 8px;
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}

/* Pinnadel ganz außen (bleibt bei angepinnten Notizen sichtbar),
   Mülleimer links daneben. */
.notes-ws__item-delete {
  right: 8px;
}

.notes-ws__item:hover .notes-ws__item-delete,
.notes-ws__item:hover .notes-ws__item-pin,
.notes-ws__item-delete:focus-visible,
.notes-ws__item-pin:focus-visible,
.notes-ws__item-pin.is-active {
  opacity: 1;
}

.notes-ws__item-pin.is-active {
  color: var(--pm-accent, #006b75);
}

.notes-ws__item-pin:hover {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent, #006b75);
}

.notes-ws__item-delete:hover {
  background: color-mix(in srgb, var(--pm-danger, #d95757) 12%, transparent);
  color: var(--pm-danger, #d95757);
}


.notes-ws__item-select { border-radius:0; }
.notes-ws__item-select:hover { background:transparent; }
.notes-ws__item-delete { padding:0; }
</style>

<style scoped>
.notes-ws__groups { margin:0; padding:0 6px 76px; }
.notes-ws__group--flat { padding-top:6px; }
</style>

<style scoped>
.notes-ws__fab {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 16px;
  z-index: 5;
  isolation: isolate;
  display: flex;
  align-items: stretch;
  gap: 1px;
  border-radius: 999px;
  box-shadow: 0 6px 20px -6px rgba(0, 0, 0, 0.32), 0 2px 6px -2px rgba(0, 0, 0, 0.18);
  transition: box-shadow 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1));
}
.notes-ws__fab::before {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -16px;
  z-index: -1;
  width: 100vw;
  height: 76px;
  pointer-events: none;
  background: linear-gradient(
    to bottom,
    transparent 0%,
    color-mix(in srgb, var(--pm-content-surface, #fff) 78%, transparent) 34%,
    var(--pm-content-surface, #fff) 100%
  );
  transform: translateX(-50%);
}
.notes-ws__fab .v-btn {
  text-transform: none;
  letter-spacing: 0;
  transition:
    background-color 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1)),
    box-shadow 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1));
}
.notes-ws__fab .v-btn:hover:not(.v-btn--disabled) {
  background-color: color-mix(
    in srgb,
    rgb(var(--v-theme-primary)) 91%,
    rgb(var(--v-theme-on-primary)) 9%
  ) !important;
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, rgb(var(--v-theme-on-primary)) 28%, transparent),
    inset 0 0 0 1px color-mix(in srgb, rgb(var(--v-theme-on-primary)) 14%, transparent);
}
.notes-ws__fab:has(.v-btn:hover:not(.v-btn--disabled)) {
  box-shadow:
    0 10px 28px -10px color-mix(in srgb, rgb(var(--v-theme-primary)) 56%, transparent),
    0 4px 10px -5px rgba(0, 0, 0, 0.3),
    0 0 0 3px color-mix(in srgb, rgb(var(--v-theme-primary)) 13%, transparent);
}
.notes-ws__fab-main.v-btn {
  height: 44px;
  padding-inline: 20px 18px;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 999px;
}

@media(prefers-reduced-motion:reduce) { .notes-ws__fab,.notes-ws__fab .v-btn { transition:none; } }
</style>

<style scoped>
.thoughts-zoom { position:absolute; right:20px; bottom:20px; z-index:7; display:flex; align-items:center; padding:3px; gap:2px; border:1px solid var(--pm-divider,#d8dfe1); border-radius:9px; background:var(--pm-content-surface,#fff); box-shadow:0 2px 8px #0001; }
.thoughts-zoom button { min-width:30px; height:30px; padding:0 8px; border:0; border-radius:6px; color:inherit; font:inherit; font-size:12px; cursor:pointer; background:transparent; }
.thoughts-zoom button:hover { background:var(--pm-list-hover); }
.thoughts-board { padding-bottom:76px; }
</style>

<style scoped>
.thoughts-board { touch-action:pan-x pan-y; }
</style>

<style scoped>
.thoughts-toolbar { position:absolute; top:16px; left:calc(var(--thoughts-list-width) + (100% - var(--thoughts-list-width)) / 2); transform:translateX(-50%); z-index:7; display:flex; gap:4px; align-items:center; padding:5px; border:1px solid var(--pm-divider,#d8dfe1); border-radius:14px; color:var(--pm-text); background:var(--pm-content-surface,#fff); box-shadow:0 4px 16px #0001; }
.thoughts-toolbar>button,.thoughts-toolbar :deep(.color-trigger) { display:flex; align-items:center; justify-content:center; width:40px; height:40px; padding:0; border:0; border-radius:9px; color:inherit; background:transparent; cursor:pointer; }
.thoughts-toolbar>button:hover,.thoughts-toolbar :deep(.color-trigger:hover) { background:var(--pm-list-hover); }
.thoughts-toolbar :deep(.thought-color-picker) { margin:0; }
.thoughts-toolbar :deep(.color-trigger svg) { width:22px; height:22px; }
</style>

<style scoped>
.thoughts-board { padding-top:80px; }
.thoughts-ws.is-list-collapsed .thoughts-toolbar { left:50%; }
@media(max-width:650px) { .thoughts-toolbar { position:relative; top:auto; left:auto; transform:none; align-self:center; order:1; margin:12px 0; }.thoughts-board { order:2; padding-top:20px; }.thoughts-zoom { order:3; } }
</style>

<style scoped>
.thoughts-toolbar { background:color-mix(in srgb,var(--pm-content-surface,#fff) 78%,transparent); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); }
</style>

<style scoped>
.thoughts-toolbar-divider { flex:0 0 1px; height:24px; margin:0 4px; background:var(--pm-divider,#d8dfe1); }
.thoughts-toolbar>button:disabled { cursor:default; opacity:.4; }
.thoughts-toolbar>button:disabled:hover { background:transparent; }
</style>

<style scoped>
.notes-ws__item-delete { right:40px; }
.thoughts-item-edit { padding:0; }
@media(hover:none) { .notes-ws__item-delete,.notes-ws__item-pin { opacity:.72; } }
</style>

<style scoped>
.notes-ws__fab-main.v-btn.is-click-animated {
  transform-origin: 50% 65%;
  animation: notes-ws-fab-press 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes notes-ws-fab-press {
  0% { transform: translateY(0) scale(1); }
  18% { transform: translateY(2px) scale(0.94); }
  48% { transform: translateY(-3px) scale(1.045); }
  72% { transform: translateY(1px) scale(0.985); }
  100% { transform: translateY(0) scale(1); }
}
.notes-ws__item.is-new {
  transform-origin: 50% 0;
  animation: notes-ws-note-created 560ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes notes-ws-note-created {
  0% {
    min-height: 0;
    max-height: 0;
    opacity: 0;
    transform: translateY(18px) scale(0.92);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent) 0%, transparent);
  }
  56% {
    min-height: var(--notes-row-height);
    max-height: calc(var(--notes-row-height) + 28px);
    opacity: 1;
    transform: translateY(-4px) scale(1.025);
    box-shadow:
      0 14px 32px -16px color-mix(in srgb, var(--pm-accent) 70%, transparent),
      0 0 0 4px color-mix(in srgb, var(--pm-accent) 18%, transparent);
  }
  78% {
    min-height: var(--notes-row-height);
    max-height: calc(var(--notes-row-height) + 28px);
    opacity: 1;
    transform: translateY(2px) scale(0.992);
    box-shadow: 0 4px 14px -10px color-mix(in srgb, var(--pm-accent) 36%, transparent);
  }
  100% {
    min-height: var(--notes-row-height);
    max-height: calc(var(--notes-row-height) + 28px);
    opacity: 1;
    transform: none;
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent) 0%, transparent);
  }
}


@media(prefers-reduced-motion:reduce) { .notes-ws__item.is-new,.notes-ws__fab-main.v-btn.is-click-animated { animation:none; } }
:global(.pm-no-animations) .notes-ws__item.is-new, :global(.pm-no-animations) .notes-ws__fab-main.v-btn.is-click-animated { animation:none; }
</style>

<style scoped>
.thoughts-selection-box { position:absolute; z-index:4; pointer-events:none; border:1px solid var(--pm-accent,#26736b); background:color-mix(in srgb,var(--pm-accent,#26736b) 12%,transparent); border-radius:3px; }
.thoughts-card.is-selected { box-shadow:0 0 0 2px var(--pm-accent,#26736b),0 2px 8px #0001; }
.thoughts-toolbar>.thoughts-delete-selected { color:inherit; }
.thoughts-toolbar>.thoughts-delete-selected:hover:not(:disabled) { background:var(--pm-list-hover); }
</style>

<style scoped>
.thoughts-toolbar :deep(.color-trigger:disabled) { opacity:.4; cursor:default; }
.thoughts-toolbar :deep(.color-trigger:disabled:hover) { background:transparent; }
</style>

<style scoped>
.thoughts-dialog-name { margin:0; color:rgba(var(--v-theme-on-surface),.86); font-size:.98rem; font-weight:650; line-height:1.45; }
.thoughts-dialog-error { margin-top:12px; color:var(--pm-danger,#d95757); font-size:.84rem; }
</style>

<style scoped>
.thoughts-canvas.is-selecting,.thoughts-canvas.is-selecting * { user-select:none; -webkit-user-select:none; }
.thoughts-canvas.is-selecting textarea { pointer-events:none; }
</style>

<style scoped>
.thoughts-summary-progress p,.thoughts-summary-hint { margin-top:12px; color:var(--pm-muted); font-size:.84rem; line-height:1.5; }
</style>
